import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime, timedelta
import sqlite3
import os
import smtplib # Para enviar e-mails
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==================== Importação de bibliotecas opcionais (para gráficos) ====================
try:
    import pandas as pd
    import plotly.express as px
except ImportError:
    pd = None
    px = None
    st.error("❌ Erro: As bibliotecas 'pandas' e 'plotly' não foram encontradas. A aba de gráficos não funcionará. Por favor, verifique seu 'requirements.txt' e faça um 'Clear cache and redeploy' no Streamlit Share.")

st.set_page_config(page_title="Sistema de Validação", page_icon="🏛️", layout="wide")

# ==================== INICIALIZAÇÃO DE ESTADO ====================
if 'api_key' not in st.session_state:
    st.session_state['api_key'] = ''
if 'db_reset_needed_rerun' not in st.session_state:
    st.session_state['db_reset_needed_rerun'] = False
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'show_register_form' not in st.session_state:
    st.session_state['show_register_form'] = False

if st.session_state['db_reset_needed_rerun']:
    st.session_state['db_reset_needed_rerun'] = False
    st.experimental_rerun()

# ==================== BANCO DE DADOS ====================

def reset_database():
    """Reseta o banco de dados, removendo o arquivo e limpando o cache."""
    try:
        if os.path.exists('processos.db'):
            os.remove('processos.db')
        st.cache_resource.clear()
        st.session_state['db_reset_needed_rerun'] = True
        st.success("✅ Banco de dados resetado com sucesso! A página será recarregada.")
        st.experimental_rerun()
    except Exception as e:
        st.error(f"❌ Erro ao resetar o banco de dados: {str(e)}")
        return None

@st.cache_resource
def init_db():
    """Inicializa o banco de dados, criando tabelas se não existirem ou se o schema estiver desatualizado."""
    try:
        conn = sqlite3.connect('processos.db', check_same_thread=False)
        c = conn.cursor()

        expected_processos_column_names = [
            'id', 'numero', 'rt', 'requerente', 'analista', 'uso', 
            'tipologia', 'area', 'data_protocolo', 'status', 'data_cadastro'
        ]

        schema_outdated = False

        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processos'")
        table_exists = c.fetchone()

        if table_exists:
            c.execute("PRAGMA table_info(processos)")
            current_columns_info = c.fetchall()
            current_column_names = [col[1] for col in current_columns_info]

            if not (set(expected_processos_column_names) == set(current_column_names) and 
                    len(expected_processos_column_names) == len(current_column_names)):
                schema_outdated = True
        else:
            schema_outdated = True

        if schema_outdated:
            st.warning("⚠️ Detectada estrutura de banco de dados antiga ou inconsistente. Recriando tabelas...")
            c.execute('DROP TABLE IF EXISTS tramitacao')
            c.execute('DROP TABLE IF EXISTS analises')
            c.execute('DROP TABLE IF EXISTS processos')
            conn.commit()

            c.execute('''CREATE TABLE processos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero TEXT UNIQUE NOT NULL,
                rt TEXT NOT NULL,
                requerente TEXT NOT NULL,
                analista TEXT NOT NULL,
                uso TEXT NOT NULL,
                tipologia TEXT NOT NULL,
                area REAL NOT NULL,
                data_protocolo TEXT NOT NULL,
                status TEXT DEFAULT 'Protocolado',
                data_cadastro TEXT DEFAULT CURRENT_TIMESTAMP
            )''')
            conn.commit()

        c.execute('''CREATE TABLE IF NOT EXISTS analises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_id INTEGER NOT NULL,
            resultado TEXT NOT NULL,
            status TEXT NOT NULL,
            data_analise TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (processo_id) REFERENCES processos(id)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS tramitacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_id INTEGER NOT NULL,
            setor TEXT NOT NULL,
            data_entrada TEXT NOT NULL,
            data_saida TEXT,
            observacao TEXT,
            FOREIGN KEY (processo_id) REFERENCES processos(id)
        )''')

        conn.commit()
        return conn
    except Exception as e:
        st.error(f"❌ Erro ao inicializar o banco de dados: {str(e)}")
        return None

conn = init_db()

# ==================== FUNÇÕES DE DADOS ====================

def cadastrar(numero, rt, requerente, analista, uso, tipologia, area, data_protocolo):
    """Cadastra um novo processo no banco de dados."""
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        c.execute('''INSERT INTO processos 
                    (numero, rt, requerente, analista, uso, tipologia, area, data_protocolo) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                 (numero, rt, requerente, analista, uso, tipologia, area, data_protocolo))
        conn.commit()
        return True, "✅ Processo cadastrado com sucesso!"
    except sqlite3.IntegrityError:
        return False, "❌ Erro: Já existe um processo com este número. Por favor, use um número único."
    except Exception as e:
        return False, f"❌ Erro ao cadastrar: {str(e)}"

def listar():
    """Lista todos os processos cadastrados."""
    if not conn: return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM processos ORDER BY id DESC')
        return c.fetchall()
    except Exception as e:
        st.error(f"❌ Erro ao listar processos: {str(e)}")
        return []

def buscar_por_numero(numero):
    """Busca um processo pelo número."""
    if not conn: return None
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM processos WHERE numero = ?', (numero,))
        return c.fetchone()
    except Exception as e:
        st.error(f"❌ Erro ao buscar processo: {str(e)}")
        return None

def atualizar(pid, numero, rt, requerente, analista, uso, tipologia, area, data_protocolo):
    """Atualiza os dados de um processo existente."""
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        c.execute('''UPDATE processos 
                    SET numero=?, rt=?, requerente=?, analista=?, uso=?, tipologia=?, area=?, data_protocolo=?
                    WHERE id=?''',
                 (numero, rt, requerente, analista, uso, tipologia, area, data_protocolo, pid))
        conn.commit()
        return True, "✅ Processo atualizado com sucesso!"
    except sqlite3.IntegrityError:
        return False, "❌ Erro: Número de processo já existe! Por favor, use um número único."
    except Exception as e:
        return False, f"❌ Erro ao atualizar processo: {str(e)}"

def deletar(pid):
    """Deleta um processo e suas tramitações/análises associadas."""
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        c.execute('DELETE FROM analises WHERE processo_id = ?', (pid,))
        c.execute('DELETE FROM tramitacao WHERE processo_id = ?', (pid,))
        c.execute('DELETE FROM processos WHERE id = ?', (pid,))
        conn.commit()
        return True, "✅ Processo deletado com sucesso!"
    except Exception as e:
        return False, f"❌ Erro ao deletar processo: {str(e)}"

def atualizar_status(pid, novo_status):
    """Atualiza o status de um processo."""
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        c.execute('UPDATE processos SET status = ? WHERE id = ?', (novo_status, pid))
        conn.commit()
        return True, "✅ Status atualizado!"
    except Exception as e:
        return False, f"❌ Erro ao atualizar status: {str(e)}" 

# ==================== FUNÇÕES CRUD (TRAMITAÇÃO) ====================

def registrar_tramitacao(processo_id, setor, data_entrada, data_saida=None, observacao=""):
    """Registra uma nova movimentação de tramitação para um processo."""
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        c.execute('''UPDATE tramitacao 
                    SET data_saida = ? 
                    WHERE processo_id = ? AND data_saida IS NULL''', 
                 (data_entrada, processo_id))

        c.execute('''INSERT INTO tramitacao 
                    (processo_id, setor, data_entrada, data_saida, observacao) 
                    VALUES (?, ?, ?, ?, ?)''',
                 (processo_id, setor, data_entrada, data_saida, observacao))
        conn.commit()
        return True, "✅ Tramitação registrada com sucesso!"
    except Exception as e:
        return False, f"❌ Erro ao registrar tramitação: {str(e)}"

def listar_tramitacao(processo_id):
    """Lista as tramitações de um processo específico."""
    if not conn: return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM tramitacao WHERE processo_id = ? ORDER BY data_entrada DESC', (processo_id,))
        return c.fetchall()
    except Exception as e:
        st.error(f"Erro ao listar tramitações: {str(e)}")
        return []

def atualizar_tramitacao(tid, setor, data_entrada, data_saida, observacao):
    """Atualiza uma movimentação de tramitação existente."""
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        c.execute('''UPDATE tramitacao 
                    SET setor=?, data_entrada=?, data_saida=?, observacao=?
                    WHERE id=?''',
                 (setor, data_entrada, data_saida, observacao, tid))
        conn.commit()
        return True, "✅ Movimentação de tramitação atualizada com sucesso!"
    except Exception as e:
        return False, f"❌ Erro ao atualizar movimentação: {str(e)}"

def deletar_tramitacao(tid):
    """Deleta uma movimentação de tramitação."""
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        c.execute('DELETE FROM tramitacao WHERE id = ?', (tid,))
        conn.commit()
        return True, "✅ Movimentação deletada!"
    except Exception as e:
        return False, f"❌ Erro ao deletar movimentação: {str(e)}"

# ==================== FUNÇÕES CRUD (ANÁLISES) ====================

def salvar_analise(processo_id, resultado, status):
    """Salva o resultado de uma análise no banco de dados."""
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        c.execute('''INSERT INTO analises (processo_id, resultado, status) 
                    VALUES (?, ?, ?)''',
                 (processo_id, resultado, status))
        conn.commit()
        return True, "✅ Análise salva com sucesso!"
    except Exception as e:
        return False, f"❌ Erro ao salvar análise: {str(e)}"

def listar_analises(processo_id):
    """Lista as análises de um processo específico."""
    if not conn: return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM analises WHERE processo_id = ? ORDER BY data_analise DESC', (processo_id,))
        return c.fetchall()
    except Exception as e:
        st.error(f"Erro ao listar análises: {str(e)}")
        return []

# ==================== FUNÇÕES PARA GRÁFICOS ====================
def get_processos_df():
    """Carrega todos os processos para um DataFrame do pandas."""
    if not conn or pd is None: return pd.DataFrame()
    try:
        df = pd.read_sql_query("SELECT * FROM processos", conn)
        df['data_protocolo'] = pd.to_datetime(df['data_protocolo'], errors='coerce')
        df['data_cadastro'] = pd.to_datetime(df['data_cadastro'], errors='coerce')
        return df
    except Exception as e:
        st.error(f"❌ Erro ao carregar processos para DataFrame: {e}")
        return pd.DataFrame()

def get_tramitacoes_df():
    """Carrega todas as tramitações para um DataFrame do pandas."""
    if not conn or pd is None: return pd.DataFrame()
    try:
        df = pd.read_sql_query("SELECT * FROM tramitacao", conn)
        df['data_entrada'] = pd.to_datetime(df['data_entrada'], errors='coerce')
        df['data_saida'] = pd.to_datetime(df['data_saida'], errors='coerce')
        df['duracao_dias'] = (df['data_saida'] - df['data_entrada']).dt.days.fillna(0)
        return df
    except Exception as e:
        st.error(f"❌ Erro ao carregar tramitações para DataFrame: {e}")
        return pd.DataFrame()

# ==================== FUNÇÃO DE ENVIO DE E-MAIL ====================
def send_email_request(username_req, password_req, contact_email):
    recipient_email = "dayanesancoe@gmail.com" # Seu e-mail para receber as solicitações

    # Verifica se as configurações SMTP estão presentes em st.secrets
    if "smtp" not in st.secrets or \
       "sender_email" not in st.secrets["smtp"] or \
       "sender_password" not in st.secrets["smtp"] or \
       "smtp_server" not in st.secrets["smtp"] or \
       "smtp_port" not in st.secrets["smtp"]:
        st.error("❌ As configurações SMTP não estão completas em '.streamlit/secrets.toml'. Não é possível enviar e-mail.")
        return False

    sender_email = st.secrets["smtp"]["sender_email"]
    sender_password = st.secrets["smtp"]["sender_password"]
    smtp_server = st.secrets["smtp"]["smtp_server"]
    smtp_port = st.secrets["smtp"]["smtp_port"]

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = "Solicitação de Criação de Usuário no Sistema de Validação"

    body = f"""
    <html>
    <body>
        <p>Uma nova solicitação de acesso foi feita para o Sistema de Validação de Processos:</p>
        <ul>
            <li><b>Usuário Desejado:</b> {username_req}</li>
            <li><b>Senha Desejada:</b> {password_req}</li>
            <li><b>E-mail para Contato:</b> {contact_email}</li>
        </ul>
        <p>Por favor, revise a solicitação e, se aprovada, adicione as credenciais ao arquivo <code>.streamlit/secrets.toml</code> na seção <code>[login]</code>.</p>
        <p>Exemplo:</p>
        <pre>
[login]
username = "admin"
password = "admin123"
{username_req}_username = "{username_req}"
{username_req}_password = "{password_req}"
        </pre>
        <p>Atenciosamente,</p>
        <p>Sistema de Validação de Processos</p>
    </body>
    </html>
    """
    msg.attach(MIMEText(body, 'html')) # Envia como HTML para melhor formatação

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls() # Inicia a criptografia TLS
            server.login(sender_email, sender_password)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"❌ Erro ao enviar e-mail: {e}")
        st.info("Verifique se as credenciais SMTP em '.streamlit/secrets.toml' estão corretas (especialmente a senha de aplicativo do Gmail, se for o caso).")
        return False

# ==================== TELAS DE LOGIN E REGISTRO ====================

def login_form():
    """Exibe o formulário de login."""
    st.title("🔒 Login no Sistema de Validação")
    st.markdown("---")

    with st.form("login_form"):
        username = st.text_input("Usuário:")
        password = st.text_input("Senha:", type="password")
        login_button = st.form_submit_button("Entrar", type="primary")

        if login_button:
            # Verifica as credenciais no secrets.toml
            login_config = st.secrets.get("login", {}) # Usa .get para evitar KeyError se [login] não existir

            if "username" in login_config and "password" in login_config:
                # Autenticação para o usuário principal (admin)
                if username == login_config["username"] and password == login_config["password"]:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = username
                    st.success("Login realizado com sucesso!")
                    st.experimental_rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
            else:
                st.error("❌ Credenciais de login não configuradas em '.streamlit/secrets.toml'.")
                st.info("Por favor, crie o arquivo '.streamlit/secrets.toml' com as credenciais de login.")

    st.markdown("---")
    if st.button("Solicitar Novo Usuário", key="show_register_button", use_container_width=True):
        st.session_state['show_register_form'] = True
        st.experimental_rerun()

def register_request_form():
    """Exibe o formulário para solicitar acesso."""
    st.title("📝 Solicitar Novo Usuário")
    st.markdown("---")

    with st.form("register_request_form"):
        username_req = st.text_input("Nome de Usuário Desejado", help="Será usado para login.")
        password_req = st.text_input("Senha Desejada", type="password", help="Será a senha para login.")
        contact_email = st.text_input("Seu E-mail (para contato)", help="Usaremos para te avisar sobre a aprovação.")

        submit_request = st.form_submit_button("Enviar Solicitação", type="primary")

        if submit_request:
            if not (username_req and password_req and contact_email):
                st.error("❌ Por favor, preencha todos os campos.")
            else:
                if send_email_request(username_req, password_req, contact_email):
                    st.success("✅ Sua solicitação de acesso foi enviada para Dayane. Você será notificado por e-mail quando for aprovada.")
                    st.session_state['show_register_form'] = False # Volta para a tela de login
                    st.experimental_rerun()
                else:
                    st.error("❌ Falha ao enviar a solicitação. Verifique as configurações SMTP e tente novamente.")

        if st.button("Voltar para Login", key="back_to_login_button", use_container_width=True):
            st.session_state['show_register_form'] = False
            st.experimental_rerun()

# ==================== CONTEÚDO PRINCIPAL DO APP (APÓS LOGIN) ====================
def main_app_content():
    # Opções para os campos de seleção
    usos_options = ["Unifamiliar", "Multifamiliar", "Serviços", "Comércio Varejista", "Comércio Atacadista", "Indústria", "Misto", "Sem destinação específica"]
    tipologias_options = ["Aprovação Inicial", "Levantamento Existente", "Modificação de Projeto", "Regularização", "Misto", "RIU", "ERB", "As Built"]
    setores_tramitacao = ["Protocolo", "Requerente", "Analista", "Fiscalização", "Parecer Externo", "Emissão de Alvará", "Arquivo"]
    status_kanban = ["Protocolado", "Em Análise", "Aguardando Correções", "Aprovado", "Reprovado"]

    # Renderiza a sidebar
    with st.sidebar:
        st.image("https://www.contagem.mg.gov.br/portal/uploads/2023/07/logo-contagem-2023.png", width=200)
        st.title(f"Bem-vindo(a), {st.session_state.get('username', 'Usuário')}!")
        st.markdown("---")

        # Entrada da API Key do Gemini
        st.subheader("🔑 API Key Google Gemini")
        st.session_state['api_key'] = st.text_input("Insira sua API Key", type="password", value=st.session_state['api_key'])
        if st.session_state['api_key']:
            try:
                genai.configure(api_key=st.session_state['api_key'])
                st.success("API Key configurada!")
            except Exception as e:
                st.error(f"Erro ao configurar API Key: {str(e)}")
        else:
            st.warning("Por favor, insira sua API Key do Google Gemini para usar a análise de PDF.")

        st.markdown("---")
        if st.button("🔄 Resetar Banco de Dados", help="Apaga todos os dados e recria as tabelas."):
            reset_database()

        st.markdown("---")
        if st.button("🚪 Sair", type="primary"):
            st.session_state['logged_in'] = False
            st.session_state['username'] = ''
            st.experimental_rerun()

        st.markdown("---")
        st.markdown("""
        <div style='text-align: center'>
            <p><strong>Desenvolvido por Dayane</strong></p>
            <p>Versão 1.0.0</p>
        </div>
        """, unsafe_allow_html=True)

    # Abas principais
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["➕ Cadastrar", "📋 Gerenciar", "🔄 Tramitação", "📊 Kanban", "🤖 Analisar", "📈 Gráficos"])

    # ==================== ABA 1: CADASTRAR ====================
    with tab1:
        st.header("➕ Cadastrar Novo Processo")

        with st.form("form_cadastro_processo"):
            st.subheader("Dados do Processo")
            numero = st.text_input("Número do Processo", help="Ex: 12345/2024") 
            rt = st.text_input("Responsável Técnico (RT)")
            requerente = st.text_input("Requerente")
            analista = st.text_input("Analista Responsável")

            col1, col2 = st.columns(2)
            with col1:
                uso = st.selectbox("Uso", usos_options)
            with col2:
                tipologia = st.selectbox("Tipologia", tipologias_options)

            area = st.number_input("Área (m²)", min_value=0.0, format="%.2f")
            data_protocolo = st.date_input("Data do Protocolo", value="today")

            submit_button = st.form_submit_button("Cadastrar Processo", type="primary")

            if submit_button:
                if not (numero and rt and requerente and analista and uso and tipologia and area > 0 and data_protocolo):
                    st.error("❌ Por favor, preencha todos os campos obrigatórios e verifique a área.")
                else:
                    sucesso, msg = cadastrar(numero, rt, requerente, analista, uso, tipologia, area, data_protocolo.strftime('%Y-%m-%d'))
                    if sucesso:
                        st.success(msg)
                        processo_recem_cadastrado = buscar_por_numero(numero)
                        if processo_recem_cadastrado:
                            registrar_tramitacao(processo_recem_cadastrado[0], "Protocolo", datetime.now().strftime('%Y-%m-%d'), None, "Cadastro inicial")
                            st.info("Primeira tramitação (Protocolo) registrada automaticamente.")
                        st.experimental_rerun()
                    else:
                        st.error(msg)

    # ==================== ABA 2: GERENCIAR ====================
    with tab2:
        st.header("📋 Gerenciamento de Processos")

        processos = listar()

        if not processos:
            st.info("📭 Nenhum processo cadastrado ainda. Use a aba 'Cadastrar' para adicionar novos processos.")
        else:
            st.subheader("Lista de Processos Cadastrados")
            for p in processos:
                status_icon = "🔵"
                if p[9] == "Aprovado": status_icon = "✅"
                elif p[9] == "Reprovado": status_icon = "❌"
                elif p[9] == "Aguardando Correções": status_icon = "🟠"
                elif p[9] == "Em Análise": status_icon = "🔎"

                with st.expander(f"{status_icon} **{p[1]}** - {p[3]} ({p[6]})"):
                    st.markdown(f"**Número:** {p[1]}")
                    st.markdown(f"**RT:** {p[2]}")
                    st.markdown(f"**Requerente:** {p[3]}")
                    st.markdown(f"**Analista:** {p[4]}")
                    st.markdown(f"**Uso:** {p[5]}")
                    st.markdown(f"**Tipologia:** {p[6]}")
                    st.markdown(f"**Área (m²):** {p[7]:.2f}")
                    st.markdown(f"**Data Protocolo:** {datetime.strptime(p[8], '%Y-%m-%d').strftime('%d/%m/%Y')}")
                    st.markdown(f"**Status:** {p[9]}")
                    st.markdown(f"**Cadastrado em:** {datetime.strptime(p[10], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')}")

                    col_edit, col_del = st.columns(2)
                    with col_edit:
                        if st.button("✏️ Editar Processo", key=f"edit_proc_{p[0]}", use_container_width=True):
                            st.session_state[f"edit_mode_{p[0]}"] = not st.session_state.get(f"edit_mode_{p[0]}", False)
                    with col_del:
                        if st.button("🗑️ Deletar Processo", key=f"delete_proc_{p[0]}", type="secondary", use_container_width=True):
                            if st.warning(f"Tem certeza que deseja deletar o processo {p[1]}? Esta ação é irreversível e deletará todas as tramitações e análises associadas."):
                                if st.button("CONFIRMAR DELEÇÃO", key=f"confirm_delete_proc_{p[0]}", type="danger"):
                                    sucesso, msg = deletar(p[0])
                                    if sucesso:
                                        st.success(msg)
                                        st.experimental_rerun()
                                    else:
                                        st.error(msg)

                    if st.session_state.get(f"edit_mode_{p[0]}", False):
                        st.markdown("##### Editando Processo")
                        with st.form(f"form_editar_processo_{p[0]}"):
                            ed_numero = st.text_input("Número do Processo", value=p[1], key=f"ed_numero_{p[0]}")
                            ed_rt = st.text_input("RT", value=p[2], key=f"ed_rt_{p[0]}")
                            ed_requerente = st.text_input("Requerente", value=p[3], key=f"ed_requerente_{p[0]}")
                            ed_analista = st.text_input("Analista", value=p[4], key=f"ed_analista_{p[0]}")

                            try:
                                current_uso_index = usos_options.index(p[5])
                            except ValueError:
                                current_uso_index = 0
                            ed_uso = st.selectbox("Uso", usos_options, index=current_uso_index, key=f"ed_uso_{p[0]}")

                            try:
                                current_tipologia_index = tipologias_options.index(p[6])
                            except ValueError:
                                current_tipologia_index = 0
                            ed_tipologia = st.selectbox("Tipologia", tipologias_options, index=current_tipologia_index, key=f"ed_tipologia_{p[0]}")

                            ed_area = st.number_input("Área (m²)", value=float(p[7]), min_value=0.0, format="%.2f", key=f"ed_area_{p[0]}")

                            try:
                                default_date_protocolo = datetime.strptime(p[8], '%Y-%m-%d').date()
                            except (ValueError, TypeError):
                                default_date_protocolo = datetime.now().date()
                            ed_data_protocolo = st.date_input("Data do Protocolo", value=default_date_protocolo, key=f"ed_data_protocolo_{p[0]}")

                            if st.form_submit_button("Salvar Alterações", type="primary"):
                                if not ed_numero or not ed_rt or not ed_requerente or not ed_analista or not ed_uso or not ed_tipologia or ed_area <= 0 or not ed_data_protocolo:
                                    st.error("Por favor, preencha todos os campos obrigatórios e verifique a área.")
                                else:
                                    sucesso, msg = atualizar(p[0], ed_numero, ed_rt, ed_requerente, ed_analista, ed_uso, ed_tipologia, ed_area, ed_data_protocolo.strftime('%Y-%m-%d'))
                                    if sucesso:
                                        st.success(msg)
                                        st.session_state[f"edit_mode_{p[0]}"] = False
                                        st.experimental_rerun()
                                    else:
                                        st.error(msg)

    # ==================== ABA 3: TRAMITAÇÃO ====================
    with tab3:
        st.header("🔄 Gerenciamento de Tramitação")

        processos_tramitacao = listar()
        if not processos_tramitacao:
            st.info("📭 Nenhum processo cadastrado para gerenciar tramitação.")
        else:
            processo_options = [(p[0], p[1]) for p in processos_tramitacao]

            default_index = 0
            if 'selected_processo_tramitacao_id' in st.session_state and st.session_state['selected_processo_tramitacao_id'] in [p[0] for p in processo_options]:
                default_index = [p[0] for p in processo_options].index(st.session_state['selected_processo_tramitacao_id'])

            processo_selecionado_tuple = st.selectbox(
                "Selecione o Processo para Tramitação:",
                options=processo_options,
                format_func=lambda x: f"{x[1]}",
                index=default_index,
                key="select_processo_tramitacao"
            )

            if processo_selecionado_tuple:
                pid_tramitacao = processo_selecionado_tuple[0]
                st.session_state['selected_processo_tramitacao_id'] = pid_tramitacao

                processo_dados = buscar_por_numero(processo_selecionado_tuple[1])

                if processo_dados:
                    st.subheader(f"Movimentações do Processo: {processo_dados[1]}")

                    with st.form("nova_tramitacao"):
                        st.markdown("#### Registrar Nova Movimentação")
                        col_t1, col_t2 = st.columns(2)
                        with col_t1:
                            setor_novo = st.selectbox("Setor", setores_tramitacao, key="setor_novo")
                            data_entrada_nova = st.date_input("Data de Entrada", value="today", key="data_entrada_nova")
                        with col_t2:
                            data_saida_nova = st.date_input("Data de Saída (opcional)", value=None, key="data_saida_nova")
                            observacao_nova = st.text_area("Observações", key="observacao_nova")

                        if st.form_submit_button("Registrar Movimentação", type="primary"):
                            if not data_entrada_nova:
                                st.error("❌ A Data de Entrada é obrigatória.")
                            else:
                                sucesso, msg = registrar_tramitacao(
                                    pid_tramitacao, 
                                    setor_novo, 
                                    data_entrada_nova.strftime('%Y-%m-%d'), 
                                    data_saida_nova.strftime('%Y-%m-%d') if data_saida_nova else None,
                                    observacao_nova
                                )
                                if sucesso:
                                    st.success(msg)
                                    st.experimental_rerun()
                                else:
                                    st.error(msg)

                st.divider()
                st.markdown("#### Histórico de Tramitação")
                tramitacoes = listar_tramitacao(pid_tramitacao)

                if not tramitacoes:
                    st.info("📭 Nenhuma movimentação registrada para este processo.")
                else:
                    tempos_por_setor = {}
                    for i in range(len(tramitacoes)):
                        t = tramitacoes[i]
                        setor = t[2]
                        data_entrada_str = t[3]
                        data_saida_str = t[4]

                        data_entrada = datetime.strptime(data_entrada_str, '%Y-%m-%d')
                        data_saida = None
                        if data_saida_str:
                            data_saida = datetime.strptime(data_saida_str, '%Y-%m-%d')

                        if data_saida:
                            duracao = (data_saida - data_entrada).days
                            tempos_por_setor[setor] = tempos_por_setor.get(setor, 0) + duracao
                        elif i == len(tramitacoes) - 1:
                            duracao = (datetime.now() - data_entrada).days
                            tempos_por_setor[setor] = tempos_por_setor.get(setor, 0) + duracao

                    st.markdown("##### ⏱️ Tempo Acumulado por Setor:")
                    cols_metrics = st.columns(len(setores_tramitacao))
                    for idx, setor in enumerate(setores_tramitacao):
                        with cols_metrics[idx]:
                            st.metric(setor, f"{tempos_por_setor.get(setor, 0)} dias")

                    st.divider()

                    for t in tramitacoes:
                        icon = "➡️"
                        if t[2] == "Protocolo": icon = "📝"
                        elif t[2] == "Requerente": icon = "👤"
                        elif t[2] == "Analista": icon = "👨‍💻"
                        elif t[2] == "Fiscalização": icon = "🔍"
                        elif t[2] == "Parecer Externo": icon = "🏢"
                        elif t[2] == "Emissão de Alvará": icon = "📜"
                        elif t[2] == "Arquivo": icon = "🗄️"

                        data_saida_display = datetime.strptime(t[4], '%Y-%m-%d').strftime('%d/%m/%Y') if t[4] else "Em andamento"

                        if f"edit_tram_mode_{t[0]}" not in st.session_state:
                            st.session_state[f"edit_tram_mode_{t[0]}"] = False

                        with st.expander(f"{icon} {t[2]} - Entrada: {datetime.strptime(t[3], '%Y-%m-%d').strftime('%d/%m/%Y')} - Saída: {data_saida_display}"):
                            if not st.session_state.get(f"edit_tram_mode_{t[0]}", False):
                                st.markdown(f"**Setor:** {t[2]}")
                                st.markdown(f"**Data de Entrada:** {datetime.strptime(t[3], '%Y-%m-%d').strftime('%d/%m/%Y')}")
                                st.markdown(f"**Data de Saída:** {data_saida_display}")
                                st.markdown(f"**Observações:** {t[5] if t[5] else 'Nenhuma'}")

                                col_tedit, col_tdel = st.columns(2)
                                with col_tedit:
                                    if st.button("✏️ Editar Movimentação", key=f"edit_tram_btn_{t[0]}", use_container_width=True):
                                        st.session_state[f"edit_tram_mode_{t[0]}"] = True
                                        st.experimental_rerun()
                                with col_tdel:
                                    if st.button("🗑️ Deletar Movimentação", key=f"delete_tram_btn_{t[0]}", type="secondary", use_container_width=True):
                                        st.warning(f"Tem certeza que deseja deletar esta movimentação ({t[2]})?")
                                        if st.button("CONFIRMAR DELEÇÃO", key=f"confirm_delete_tram_btn_{t[0]}", type="danger"):
                                            sucesso, msg = deletar_tramitacao(t[0])
                                            if sucesso:
                                                st.success(msg)
                                                st.experimental_rerun()
                                            else:
                                                st.error(msg)
                            else:
                                st.markdown("##### Editando Movimentação")
                                with st.form(f"form_editar_tramitacao_{t[0]}"):
                                    ed_setor = st.selectbox("Setor", setores_tramitacao, index=setores_tramitacao.index(t[2]), key=f"ed_setor_{t[0]}")
                                    ed_data_entrada = st.date_input("Data de Entrada", value=datetime.strptime(t[3], '%Y-%m-%d').date(), key=f"ed_data_entrada_{t[0]}")
                                    ed_data_saida_val = datetime.strptime(t[4], '%Y-%m-%d').date() if t[4] else None
                                    ed_data_saida = st.date_input("Data de Saída", value=ed_data_saida_val, key=f"ed_data_saida_{t[0]}")
                                    ed_observacao = st.text_area("Observações", value=t[5], key=f"ed_observacao_{t[0]}")

                                    col_tsave, col_tcancel = st.columns(2)
                                    if col_tsave.form_submit_button("Salvar Edição", type="primary"):
                                        if not (ed_setor and ed_data_entrada):
                                            st.error("❌ O Setor e a Data de Entrada são obrigatórios.")
                                        else:
                                            sucesso, msg = atualizar_tramitacao(
                                                t[0], 
                                                ed_setor, 
                                                ed_data_entrada.strftime('%Y-%m-%d'), 
                                                ed_data_saida.strftime('%Y-%m-%d') if ed_data_saida else None,
                                                ed_observacao
                                            )
                                            if sucesso:
                                                st.success(msg)
                                                st.session_state[f"edit_tram_mode_{t[0]}"] = False
                                                st.experimental_rerun()
                                            else:
                                                st.error(msg)
                                    if col_tcancel.form_submit_button("Cancelar"):
                                        st.session_state[f"edit_tram_mode_{t[0]}"] = False
                                        st.experimental_rerun()
                        st.markdown("---")

    # ==================== ABA 4: KANBAN ====================
    with tab4:
        st.header("📊 Quadro Kanban de Processos")

        processos_kanban = listar()

        if not processos_kanban:
            st.info("📭 Nenhum processo cadastrado para exibir no Kanban.")
        else:
            processos_por_status = {status: [] for status in status_kanban}
            for p in processos_kanban:
                processos_por_status[p[9]].append(p)

            cols = st.columns(len(status_kanban))

            for i, status in enumerate(status_kanban):
                with cols[i]:
                    st.subheader(f"{status} ({len(processos_por_status[status])})")
                    st.markdown("---")

                    for p in processos_por_status[status]:
                        card_color = "lightgray"
                        if status == "Aprovado": card_color = "lightgreen"
                        elif status == "Reprovado": card_color = "lightcoral"
                        elif status == "Em Análise": card_color = "lightblue"
                        elif status == "Aguardando Correções": card_color = "lightgoldenrodyellow"

                        st.markdown(f"""
                        <div style="background-color: {card_color}; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                            <p><strong>Processo:</strong> {p[1]}</p>
                            <p><strong>Requerente:</strong> {p[3]}</p>
                            <p><strong>Tipologia:</strong> {p[6]}</p>
                            <p><strong>Protocolo:</strong> {datetime.strptime(p[8], '%Y-%m-%d').strftime('%d/%m/%Y')}</p>
                            <p><strong>Analista:</strong> {p[4]}</p>
                        </div>
                        """, unsafe_allow_html=True)

                        current_status_index = status_kanban.index(status)

                        if current_status_index > 0:
                            if st.button(f"⬅️ Mover para {status_kanban[current_status_index-1]}", key=f"move_prev_{p[0]}"):
                                sucesso, msg = atualizar_status(p[0], status_kanban[current_status_index-1])
                                if sucesso: st.experimental_rerun()
                                else: st.error(msg)

                        if current_status_index < len(status_kanban) - 1:
                            if st.button(f"➡️ Mover para {status_kanban[current_status_index+1]}", key=f"move_next_{p[0]}"):
                                sucesso, msg = atualizar_status(p[0], status_kanban[current_status_index+1])
                                if sucesso: st.experimental_rerun()
                                else: st.error(msg)
                        st.markdown("---")

    # ==================== ABA 5: ANALISAR ====================
    with tab5:
        st.header("🤖 Análise de Projetos com IA")

        if not st.session_state['api_key']:
            st.warning("⚠️ Configure sua API Key do Google Gemini na barra lateral para usar esta função.")
            st.info("Como obter: Acesse https://aistudio.google.com/app/apikey e crie uma chave gratuita.")
            st.stop()

        processos_analise = listar()
        if not processos_analise:
            st.info("📭 Nenhum processo cadastrado para análise.")
        else:
            processo_selecionado_analise = st.selectbox(
                "Selecione o Processo para Análise:",
                options=[(p[0], p[1]) for p in processos_analise],
                format_func=lambda x: f"{x[1]} - {buscar_por_numero(x[1])[3]}",
                key="select_processo_analise"
            )

            if processo_selecionado_analise:
                pid_analise = processo_selecionado_analise[0]
                dados = buscar_por_numero(processo_selecionado_analise[1])

                if dados:
                    st.subheader(f"Analisando Processo: {dados[1]} - Requerente: {dados[3]}")
                    st.markdown(f"**Status Atual:** {dados[9]}")

                    st.divider()
                    st.markdown("#### 📄 Anexar Documentos")
                    col_proj, col_leg = st.columns(2)
                    with col_proj:
                        st.subheader("🏗️ Projeto Arquitetônico")
                        proj = st.file_uploader("PDFs do Projeto", type=['pdf'], accept_multiple_files=True, key="proj_upload")
                    with col_leg:
                        st.subheader("📜 Legislação Municipal")
                        leg = st.file_uploader("PDFs da Legislação", type=['pdf'], accept_multiple_files=True, key="leg_upload")

                    st.divider()
                    regras = st.text_area("📏 Regras Específicas a Verificar (Artigos da Lei, etc.):", height=150, 
                                          placeholder="Ex: Art. 10 - Área mínima de 50m² para lotes residenciais. Art. 15 - Recuo frontal de 3m.",
                                          key="regras_ia")

                    st.divider()

                    if st.button("🔍 INICIAR ANÁLISE COM IA", type="primary", use_container_width=True):
                        if not st.session_state['api_key']:
                            st.error("❌ Por favor, insira sua API Key do Google Gemini na barra lateral para iniciar a análise.")
                        elif not proj:
                            st.error("❌ Anexe pelo menos 1 PDF do projeto!")
                        elif not leg:
                            st.error("❌ Anexe pelo menos 1 PDF da legislação!")
                        elif not regras:
                            st.error("❌ Digite as regras que devem ser verificadas!")
                        else:
                            with st.spinner("🤖 Analisando projeto com Inteligência Artificial... Isso pode levar alguns minutos..."):
                                try:
                                    genai.configure(api_key=st.session_state['api_key'])

                                    txt_proj = ""
                                    for pdf in proj:
                                        reader = PyPDF2.PdfReader(pdf)
                                        for page in reader.pages:
                                            txt_proj += page.extract_text() or ""

                                    txt_leg = ""
                                    for pdf in leg:
                                        reader = PyPDF2.PdfReader(pdf)
                                        for page in reader.pages:
                                            txt_leg += page.extract_text() or ""

                                    model = None
                                    for nome in ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']:
                                        try:
                                            model = genai.GenerativeModel(nome)
                                            st.info(f"✅ Usando modelo: {nome}")
                                            break
                                        except Exception as e:
                                            continue

                                    if not model:
                                        st.error("❌ Nenhum modelo do Gemini disponível. Verifique sua API Key e a disponibilidade dos modelos.")
                                        st.stop()

                                    prompt = f"""Você é um analista técnico especializado em projetos arquitetônicos para aprovação em prefeituras.
Analise o texto do projeto arquitetônico fornecido abaixo, considerando as seguintes informações do processo:

- **Número do Processo:** {dados[1]}
- **Responsável Técnico (RT):** {dados[2]}
- **Requerente:** {dados[3]}
- **Analista:** {dados[4]}
- **Uso Predominante:** {dados[5]}
- **Tipologia do Projeto:** {dados[6]}
- **Área Construída (m²):** {dados[7]}
- **Data do Protocolo:** {datetime.strptime(dados[8], '%Y-%m-%d').strftime('%d/%m/%Y')}

Com base no texto do projeto e nas informações acima, forneça um parecer técnico detalhado.
O parecer deve incluir:
1.  **Resumo do Projeto:** Uma breve descrição do que o projeto propõe.
2.  **Conformidade:** Pontos em que o projeto parece estar em conformidade com normas gerais de construção e urbanismo (ex: recuos, taxa de ocupação, coeficiente de aproveitamento, ventilação, iluminação, acessibilidade, etc.).
3.  **Não Conformidade/Pendências:** Pontos que precisam de correção ou esclarecimento para a aprovação. Seja específico sobre quais itens estão em desacordo ou quais informações estão faltando.
4.  **Recomendação Final:**
    *   Se o projeto parece estar em total conformidade e pronto para aprovação, termine o parecer com a frase **"RECOMENDAÇÃO: PROJETO APROVADO"**.
    *   Se o projeto possui pendências ou não conformidades que exigem correção, termine o parecer com a frase **"RECOMENDAÇÃO: PROJETO REPROVADO"**.
    *   Se a análise for inconclusiva devido à falta de informações críticas no PDF ou se o PDF for apenas parcial, termine o parecer com a frase **"RECOMENDAÇÃO: ANÁLISE INCONCLUSIVA"**.

---
**TEXTO DO PROJETO ARQUITETÔNICO:**
{txt_proj[:15000]} # Limita o texto para evitar estouro de token
---
"""

                                    resposta = model.generate_content(prompt)
                                    texto_resposta = resposta.text

                                    status_analise = "INCONCLUSIVO"
                                    if "APROVADO" in texto_resposta.upper() and "REPROVADO" not in texto_resposta.upper():
                                        status_analise = "APROVADO"
                                        st.success("✅ PROJETO APROVADO")
                                        atualizar_status(dados[0], "Aprovado")
                                    elif "REPROVADO" in texto_resposta.upper():
                                        status_analise = "REPROVADO"
                                        st.error("❌ PROJETO REPROVADO")
                                        atualizar_status(dados[0], "Reprovado")
                                    else:
                                        st.warning("⚠️ ANÁLISE INCONCLUSIVA")
                                        atualizar_status(dados[0], "Em Análise")

                                    st.divider()

                                    st.markdown(resposta.text)

                                    salvar_analise(dados[0], resposta.text, status_analise)

                                    relatorio = f"""PREFEITURA DE CONTAGEM - MG
RELATÓRIO DE ANÁLISE TÉCNICA DE PROJETO ARQUITETÔNICO

Processo: {dados[1]}
Responsável Técnico: {dados[2]}
Requerente: {dados[3]}
Analista: {dados[4]}
Uso: {dados[5]}
Tipologia: {dados[6]}
Área Construída: {dados[7]}m²
Data do Protocolo: {datetime.strptime(dados[8], '%Y-%m-%d').strftime('%d/%m/%Y')}
Status do Processo: {dados[9]}
Data da Análise: {datetime.now().strftime('%d/%m/%Y às %H:%M')}

{'='*80}

{resposta.text}

{'='*80}
Relatório gerado automaticamente por Inteligência Artificial (Google Gemini)
Sistema de Validação de Processos - Prefeitura de Contagem
"""

                                    st.divider()

                                    st.download_button(
                                        label="📥 BAIXAR RELATÓRIO COMPLETO (TXT)",
                                        data=relatorio,
                                        file_name=f"relatorio_processo_{dados[1].replace('.', '_').replace('/', '_')}.txt",
                                        mime="text/plain",
                                        type="primary",
                                        use_container_width=True
                                    )

                                except Exception as erro:
                                    st.error(f"❌ Erro durante a análise: {str(erro)}")
                                    st.info("Verifique se sua API Key está correta e a disponibilidade dos modelos do Gemini.")

    # ==================== ABA 6: GRÁFICOS ====================
    with tab6:
        st.header("📈 Análise Gráfica dos Processos")

        if pd is None or px is None:
            st.error("❌ As bibliotecas de gráficos (pandas, plotly) não estão disponíveis. Verifique seu 'requirements.txt'.")
        else:
            procs_df = get_processos_df()

            if procs_df.empty:
                st.info("📭 Nenhum dado para gerar gráficos. Cadastre processos primeiro na aba 'Cadastrar'.")
            else:
                st.subheader("Selecione o tipo de gráfico para visualizar os dados:")
                chart_type = st.selectbox("Escolha a análise:", [
                    "Processos por Uso",
                    "Processos por Tipologia",
                    "Processos por Analista",
                    "Distribuição de Status Kanban",
                    "Área Total por Uso",
                    "Processos por Data de Protocolo"
                ])

                st.divider()

                if chart_type == "Processos por Uso":
                    st.markdown("### 📊 Quantidade de Processos por Tipo de Uso")
                    df_grouped = procs_df['uso'].value_counts().reset_index()
                    df_grouped.columns = ['Uso', 'Quantidade']
                    fig = px.bar(df_grouped, x='Uso', y='Quantidade', 
                                 title='Número de Processos por Tipo de Uso',
                                 labels={'Uso': 'Tipo de Uso', 'Quantidade': 'Número de Processos'},
                                 color='Uso', 
                                 template='plotly_white')
                    st.plotly_chart(fig, use_container_width=True)

                elif chart_type == "Processos por Tipologia":
                    st.markdown("### 📊 Quantidade de Processos por Tipologia")
                    df_grouped = procs_df['tipologia'].value_counts().reset_index()
                    df_grouped.columns = ['Tipologia', 'Quantidade']
                    fig = px.bar(df_grouped, x='Tipologia', y='Quantidade', 
                                 title='Número de Processos por Tipologia',
                                 labels={'Tipologia': 'Tipologia do Projeto', 'Quantidade': 'Número de Processos'},
                                 color='Tipologia',
                                 template='plotly_white')
                    st.plotly_chart(fig, use_container_width=True)

                elif chart_type == "Processos por Analista":
                    st.markdown("### 📊 Quantidade de Processos por Analista")
                    df_grouped = procs_df['analista'].value_counts().reset_index()
                    df_grouped.columns = ['Analista', 'Quantidade']
                    fig = px.bar(df_grouped, x='Analista', y='Quantidade', 
                                 title='Número de Processos por Analista',
                                 labels={'Analista': 'Nome do Analista', 'Quantidade': 'Número de Processos'},
                                 color='Analista',
                                 template='plotly_white')
                    st.plotly_chart(fig, use_container_width=True)

                elif chart_type == "Distribuição de Status Kanban":
                    st.markdown("### 📊 Distribuição de Processos por Status Kanban")
                    df_grouped = procs_df['status'].value_counts().reset_index()
                    df_grouped.columns = ['Status', 'Quantidade']
                    fig = px.pie(df_grouped, values='Quantidade', names='Status', 
                                 title='Distribuição Percentual de Processos por Status',
                                 hole=0.3, 
                                 template='plotly_white')
                    st.plotly_chart(fig, use_container_width=True)

                elif chart_type == "Área Total por Uso":
                    st.markdown("### 📊 Área Construída Total por Tipo de Uso")
                    df_grouped = procs_df.groupby('uso')['area'].sum().reset_index()
                    df_grouped.columns = ['Uso', 'Area Total (m²)']
                    fig = px.bar(df_grouped, x='Uso', y='Area Total (m²)', 
                                 title='Área Construída Total por Tipo de Uso',
                                 labels={'Uso': 'Tipo de Uso', 'Area Total (m²)': 'Área Total (m²)'},
                                 color='Uso',
                                 template='plotly_white')
                    st.plotly_chart(fig, use_container_width=True)

                elif chart_type == "Processos por Data de Protocolo":
                    st.markdown("### 📊 Número de Processos Protocolados ao Longo do Tempo")
                    df_valid_dates = procs_df.dropna(subset=['data_protocolo'])
                    if not df_valid_dates.empty:
                        df_grouped = df_valid_dates.groupby(df_valid_dates['data_protocolo'].dt.to_period('M')).size().reset_index(name='Quantidade')
                        df_grouped['data_protocolo'] = df_grouped['data_protocolo'].dt.to_timestamp()

                        fig = px.line(df_grouped, x='data_protocolo', y='Quantidade', 
                                      title='Processos Protocolados por Mês',
                                      labels={'data_protocolo': 'Mês de Protocolo', 'Quantidade': 'Número de Processos'},
                                      template='plotly_white')
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("Nenhum processo com data de protocolo válida para este gráfico.")

# ==================== LÓGICA PRINCIPAL DO APP ====================
if st.session_state['show_register_form']:
    register_request_form()
elif not st.session_state['logged_in']:
    login_form()
else:
    main_app_content()

# Rodapé
st.divider()
st.markdown("---")
st.markdown("""
<div style='text-align: center'>
    <p><strong>🏛️ Sistema de Validação de Processos com Inteligência Artificial</strong></p>
    <p>Prefeitura de Contagem - MG • Setor de Liberação de Alvarás de Construção</p>
    <p style='font-size: 0.85em; color: #666;'>Powered by Google Gemini, Streamlit, Plotly & Pandas</p>
</div>
""", unsafe_allow_html=True)

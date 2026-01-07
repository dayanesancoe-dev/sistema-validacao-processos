import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime, timedelta
import sqlite3
import os

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
if 'username' not in st.session_state: 
    st.session_state['username'] = None

if st.session_state['db_reset_needed_rerun']:
    st.session_state['db_reset_needed_rerun'] = False
    st.rerun()
 
# ==================== BANCO DE DADOS ====================

@st.cache_resource
def init_db():
    """Inicializa o banco de dados, criando tabelas se não existirem."""
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

# ==================== FUNÇÕES CRUD (PROCESSOS) ====================

def cadastrar(numero, rt, requerente, analista, uso, tipologia, area, data_protocolo):
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
    if not conn: return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM processos ORDER BY id DESC')
        return c.fetchall()
    except Exception as e:
        st.error(f"❌ Erro ao listar processos: {str(e)}")
        return []

def buscar_por_numero(numero):
    if not conn: return None
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM processos WHERE numero = ?', (numero,))
        return c.fetchone()
    except Exception as e:
        st.error(f"❌ Erro ao buscar processo: {str(e)}")
        return []

def atualizar(pid, numero, rt, requerente, analista, uso, tipologia, area, data_protocolo):
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
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        c.execute('''UPDATE tramitacao 
                    SET data_saida = ? 
                    WHERE processo_id = ? AND data_saida IS NULL''', 
                 (data_entrada.strftime('%Y-%m-%d'), processo_id))

        c.execute('''INSERT INTO tramitacao 
                    (processo_id, setor, data_entrada, data_saida, observacao) 
                    VALUES (?, ?, ?, ?, ?)''',
                 (processo_id, setor, data_entrada.strftime('%Y-%m-%d'), data_saida.strftime('%Y-%m-%d') if data_saida else None, observacao))
        conn.commit()
        return True, "✅ Tramitação registrada com sucesso!"
    except Exception as e:
        return False, f"❌ Erro ao registrar tramitação: {str(e)}"

def listar_tramitacao(processo_id):
    if not conn: return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM tramitacao WHERE processo_id = ? ORDER BY data_entrada DESC', (processo_id,))
        return c.fetchall()
    except Exception as e:
        st.error(f"Erro ao listar tramitações: {str(e)}")
        return []

def atualizar_tramitacao(tid, setor, data_entrada, data_saida, observacao):
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        c.execute('''UPDATE tramitacao 
                    SET setor=?, data_entrada=?, data_saida=?, observacao=?
                    WHERE id=?''',
                 (setor, data_entrada, data_saida, observacao, tid))
        conn.commit()
        return True, "✅ Movimentação atualizada!"
    except Exception as e:
        return False, f"❌ Erro ao atualizar movimentação: {str(e)}"

def deletar_tramitacao(tid):
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
    if not conn: return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM analises WHERE processo_id = ? ORDER BY data_analise DESC', (processo_id,))
        return c.fetchall()
    except Exception as e:
        st.error(f"Erro ao listar análises: {str(e)}")
        return []

# ==================== FUNÇÕES DE GRÁFICOS ====================
def get_processos_df():
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

# ==================== TELAS DE LOGIN ====================

def login_form():
    st.title("Login no Sistema de Validação 🏛️")
    st.markdown("---")

    with st.form("login_form"):
        username = st.text_input("Usuário", key="login_username")
        password = st.text_input("Senha", type="password", key="login_password")
        submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)

        if submitted:
            admin_username = st.secrets.get("admin_user", {}).get("username")
            admin_password = st.secrets.get("admin_user", {}).get("password")

            if admin_username is None or admin_password is None:
                st.error("❌ Credenciais de administrador não configuradas corretamente no '.streamlit/secrets.toml'.")
                st.info("Por favor, verifique se a seção '[admin_user]' com 'username' e 'password' está presente e correta.")
                return

            if username == admin_username and password == admin_password:
                st.session_state['logged_in'] = True
                st.session_state['username'] = username
                st.success(f"Login realizado com sucesso! Bem-vindo(a), {username}!")
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")

    st.info("Para acessar o sistema, use o usuário 'admin' e a senha que você configurou no arquivo '.streamlit/secrets.toml'.")


# ==================== CONTEÚDO PRINCIPAL DO APP ====================

def main_app_content():
    # Opções para os campos de seleção
    usos_options = ["Unifamiliar", "Multifamiliar", "Serviços", "Comércio Varejista", "Comércio Atacadista", "Indústria", "Misto", "Sem destinação específica"]
    tipologias_options = ["Aprovação Inicial", "Levantamento Existente", "Modificação de Projeto", "Regularização", "Misto", "RIU", "ERB", "As Built"]
    setores_tramitacao = ["Protocolo", "Requerente", "Analista", "Fiscalização", "Parecer Externo", "Emissão de Alvará", "Arquivo"]
    status_kanban = ["Protocolado", "Em Análise", "Aguardando Correções", "Aprovado", "Reprovado"]

    st.sidebar.title("🏛️ Sistema de Validação")
    st.sidebar.markdown(f"Bem-vindo(a), **{st.session_state.get('username', 'Usuário')}**!")
    st.sidebar.image("https://www.contagem.mg.gov.br/portal/uploads/2023/07/logo-contagem-2023.png", width=200)
    st.sidebar.markdown("---")

    if st.sidebar.button("Sair", type="secondary", key="sidebar_logout_button"): 
        st.session_state['logged_in'] = False
        st.session_state['username'] = None
        st.rerun()

    st.sidebar.markdown("---")
    
    st.sidebar.subheader("⚙️ Configurações de IA")
    st.session_state['api_key'] = st.sidebar.text_input(
        "Sua API Key do Google Gemini:",
        value=st.session_state['api_key'],
        type="password",
        help="Insira sua chave de API do Google Gemini para usar a análise de IA. Obtenha uma em https://aistudio.google.com/app/apikey",
        key="sidebar_api_key"
    )
    if st.session_state['api_key']:
        try:
            genai.configure(api_key=st.session_state['api_key'])
            st.sidebar.success("API Key configurada!")
        except Exception as e:
            st.sidebar.error(f"Erro ao configurar API Key: {str(e)}")
    else:
        st.sidebar.warning("API Key não configurada. A análise de IA não funcionará.")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "➕ Cadastrar", "📝 Listar", "🔄 Tramitação", "📊 Kanban", "🤖 Análise IA", "📈 Gráficos"
    ])

    # ==================== ABA 1: CADASTRAR ====================
    with tab1:
        st.header("➕ Cadastrar Novo Processo")
        with st.form("cadastro_processo"):
            col1, col2 = st.columns(2)
            with col1:
                numero = st.text_input("Número do Processo", help="Número único de identificação do processo.", key="cad_numero")
                rt = st.text_input("Responsável Técnico", key="cad_rt")
                uso = st.selectbox("Uso", usos_options, key="cad_uso")
                area = st.number_input("Área Construída (m²)", min_value=0.0, format="%.2f", key="cad_area")
            with col2:
                requerente = st.text_input("Requerente", key="cad_requerente")
                analista = st.text_input("Analista Responsável", key="cad_analista")
                tipologia = st.selectbox("Tipologia", tipologias_options, key="cad_tipologia")
                data_protocolo = st.date_input("Data do Protocolo", value="today", key="cad_data_protocolo")

            submitted = st.form_submit_button("Cadastrar Processo", type="primary", use_container_width=True)
            if submitted:
                if numero and rt and requerente and analista and uso and tipologia and area is not None and data_protocolo:
                    sucesso, msg = cadastrar(numero, rt, requerente, analista, uso, tipologia, area, data_protocolo.strftime('%Y-%m-%d'))
                    if sucesso:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.error("❌ Por favor, preencha todos os campos obrigatórios.")

    # ==================== ABA 2: LISTAR (CORRIGIDA) ====================
    with tab2:
        st.header("📝 Listar e Gerenciar Processos")
        processos = listar()
        if not processos:
            st.info("📭 Nenhum processo cadastrado ainda.")
        else:
            df_processos = pd.DataFrame(processos, columns=[
                "ID", "Número", "RT", "Requerente", "Analista", "Uso", 
                "Tipologia", "Área (m²)", "Data Protocolo", "Status", "Data Cadastro"
            ])
            df_processos['Data Protocolo'] = pd.to_datetime(df_processos['Data Protocolo']).dt.strftime('%d/%m/%Y')
            df_processos['Data Cadastro'] = pd.to_datetime(df_processos['Data Cadastro']).dt.strftime('%d/%m/%Y %H:%M')

            st.dataframe(df_processos, use_container_width=True)

            st.subheader("Atualizar ou Deletar Processo")
            col_sel, col_btn = st.columns([3, 1])
            with col_sel:
                processo_selecionado_id = st.selectbox(
                    "Selecione o Processo pelo ID ou Número:",
                    options=[(p[0], p[1]) for p in processos],
                    format_func=lambda x: f"ID: {x[0]} - Número: {x[1]}",
                    key="select_processo_edit_del"
                )

            if processo_selecionado_id:
                pid_selecionado = processo_selecionado_id[0]
                dados_processo = buscar_por_numero(processo_selecionado_id[1])

                if dados_processo:
                    with st.form(f"edit_processo_{pid_selecionado}"):
                        st.markdown(f"#### Editando Processo ID: {dados_processo[0]} - Número: {dados_processo[1]}")

                        col_e1, col_e2 = st.columns(2)
                        with col_e1:
                            edit_numero = st.text_input("Número do Processo", value=dados_processo[1], key=f"edit_numero_{pid_selecionado}")
                            edit_rt = st.text_input("Responsável Técnico", value=dados_processo[2], key=f"edit_rt_{pid_selecionado}")
                            edit_uso = st.selectbox("Uso", usos_options, index=usos_options.index(dados_processo[5]), key=f"edit_uso_{pid_selecionado}")
                            edit_area = st.number_input("Área Construída (m²)", value=float(dados_processo[7]), min_value=0.0, format="%.2f", key=f"edit_area_{pid_selecionado}")
                        with col_e2:
                            edit_requerente = st.text_input("Requerente", value=dados_processo[3], key=f"edit_requerente_{pid_selecionado}")
                            edit_analista = st.text_input("Analista Responsável", value=dados_processo[4], key=f"edit_analista_{pid_selecionado}")
                            edit_tipologia = st.selectbox("Tipologia", tipologias_options, index=tipologias_options.index(dados_processo[6]), key=f"edit_tipologia_{pid_selecionado}")
                            edit_data_protocolo = st.date_input("Data do Protocolo", value=datetime.strptime(dados_processo[8], '%Y-%m-%d').date(), key=f"edit_data_protocolo_{pid_selecionado}")

                        # CORREÇÃO DE INDENTAÇÃO AQUI: 
                        # As colunas e botões agora estão dentro do bloco 'with st.form'
                        col_upd, col_del = st.columns(2)
                        with col_upd:
                            submitted_update = st.form_submit_button("Atualizar Processo", type="primary", use_container_width=True, key=f"submit_update_{pid_selecionado}")
                        with col_del:
                            submitted_delete = st.form_submit_button("Deletar Processo", type="danger", use_container_width=True, key=f"submit_delete_{pid_selecionado}")

                    # A lógica de processamento fica FORA do form
                    if submitted_update:
                        if edit_numero and edit_rt and edit_requerente and edit_analista and edit_uso and edit_tipologia and edit_area is not None and edit_data_protocolo:
                            sucesso, msg = atualizar(pid_selecionado, edit_numero, edit_rt, edit_requerente, edit_analista, edit_uso, edit_tipologia, edit_area, edit_data_protocolo.strftime('%Y-%m-%d'))
                            if sucesso:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                        else:
                            st.error("❌ Por favor, preencha todos os campos para atualizar.")

                    if submitted_delete:
                        st.warning(f"Tem certeza que deseja deletar o processo {dados_processo[1]}? Todas as tramitações e análises associadas também serão deletadas.")
                        confirm_deletion = st.checkbox("Sim, eu confirmo a deleção deste processo.", key=f"confirm_checkbox_delete_{pid_selecionado}")
                        if confirm_deletion:
                            sucesso, msg = deletar(pid_selecionado)
                            if sucesso:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)

    # ==================== ABA 3: TRAMITAÇÃO ====================
    with tab3:
        st.header("🔄 Gerenciar Tramitação de Processos")
        processos_tramitacao = listar()
        if not processos_tramitacao:
            st.info("📭 Nenhum processo cadastrado para gerenciar tramitação.")
        else:
            processo_selecionado_tramitacao = st.selectbox(
                "Selecione o Processo para Tramitação:",
                options=[(p[0], p[1]) for p in processos_tramitacao],
                format_func=lambda x: f"ID: {x[0]} - Número: {x[1]}",
                key="select_processo_tramitacao"
            )

            if processo_selecionado_tramitacao:
                pid_tramitacao = processo_selecionado_tramitacao[0]
                dados_processo_tramitacao = buscar_por_numero(processo_selecionado_tramitacao[1])

                if dados_processo_tramitacao:
                    st.subheader(f"Tramitação do Processo: {dados_processo_tramitacao[1]} - Requerente: {dados_processo_tramitacao[3]}")

                    st.markdown("#### Registrar Nova Movimentação")
                    with st.form(f"form_nova_tramitacao_{pid_tramitacao}"):
                        col_t1, col_t2 = st.columns(2)
                        with col_t1:
                            setor = st.text_input("Setor de Destino", key=f"tram_setor_{pid_tramitacao}")
                            data_entrada = st.date_input("Data de Entrada", value="today", key=f"tram_data_entrada_{pid_tramitacao}")
                        with col_t2:
                            data_saida = st.date_input("Data de Saída (Opcional)", value=None, key=f"tram_data_saida_{pid_tramitacao}")
                            observacao = st.text_area("Observação", key=f"tram_obs_{pid_tramitacao}")

                        submitted_tram = st.form_submit_button("Registrar Tramitação", type="primary", use_container_width=True, key=f"submit_tram_{pid_tramitacao}")
                        if submitted_tram:
                            if setor and data_entrada:
                                sucesso, msg = registrar_tramitacao(pid_tramitacao, setor, data_entrada, data_saida, observacao)
                                if sucesso:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)
                            else:
                                st.error("❌ Por favor, preencha o setor e a data de entrada.")

                    st.markdown("#### Histórico de Tramitações")
                    tramitacoes = listar_tramitacao(pid_tramitacao)
                    if not tramitacoes:
                        st.info("📭 Nenhuma tramitação registrada para este processo.")
                    else:
                        df_tramitacoes = pd.DataFrame(tramitacoes, columns=[
                            "ID", "Processo ID", "Setor", "Data Entrada", "Data Saída", "Observação"
                        ])
                        df_tramitacoes['Data Entrada'] = pd.to_datetime(df_tramitacoes['Data Entrada']).dt.strftime('%d/%m/%Y')
                        df_tramitacoes['Data Saída'] = df_tramitacoes['Data Saída'].apply(lambda x: pd.to_datetime(x).strftime('%d/%m/%Y') if pd.notna(x) else 'Em Aberto')

                        st.dataframe(df_tramitacoes, use_container_width=True)

                        st.markdown("#### Editar ou Deletar Movimentação")
                        tramitacao_selecionada_id = st.selectbox(
                            "Selecione a Movimentação pelo ID:",
                            options=[t[0] for t in tramitacoes],
                            format_func=lambda x: f"ID: {x} - Setor: {next((t[2] for t in tramitacoes if t[0] == x), '')}",
                            key=f"select_tram_edit_del_{pid_tramitacao}"
                        )

                        if tramitacao_selecionada_id:
                            dados_tramitacao = next((t for t in tramitacoes if t[0] == tramitacao_selecionada_id), None)
                            if dados_tramitacao:
                                with st.form(f"form_edit_tramitacao_{tramitacao_selecionada_id}"):
                                    st.markdown(f"##### Editando Movimentação ID: {dados_tramitacao[0]}")
                                    col_et1, col_et2 = st.columns(2)
                                    with col_et1:
                                        edit_setor = st.text_input("Setor de Destino", value=dados_tramitacao[2], key=f"edit_tram_setor_{tramitacao_selecionada_id}")
                                        edit_data_entrada = st.date_input("Data de Entrada", value=datetime.strptime(dados_tramitacao[3], '%Y-%m-%d').date(), key=f"edit_tram_data_entrada_{tramitacao_selecionada_id}")
                                    with col_et2:
                                        edit_data_saida_val = datetime.strptime(dados_tramitacao[4], '%Y-%m-%d').date() if dados_tramitacao[4] else None
                                        edit_data_saida = st.date_input("Data de Saída (Opcional)", value=edit_data_saida_val, key=f"edit_tram_data_saida_{tramitacao_selecionada_id}")
                                        edit_observacao = st.text_area("Observação", value=dados_tramitacao[5], key=f"edit_tram_obs_{tramitacao_selecionada_id}")

                                    col_upd_tram, col_del_tram = st.columns(2)
                                    with col_upd_tram:
                                        submitted_update_tram = st.form_submit_button("Atualizar Movimentação", type="primary", use_container_width=True, key=f"submit_update_tram_{tramitacao_selecionada_id}")
                                    with col_del_tram:
                                        submitted_delete_tram = st.form_submit_button("Deletar Movimentação", type="danger", use_container_width=True, key=f"submit_delete_tram_{tramitacao_selecionada_id}")

                                    if submitted_update_tram:
                                        if edit_setor and edit_data_entrada:
                                            sucesso, msg = atualizar_tramitacao(tramitacao_selecionada_id, edit_setor, edit_data_entrada.strftime('%Y-%m-%d'), edit_data_saida.strftime('%Y-%m-%d') if edit_data_saida else None, edit_observacao)
                                            if sucesso:
                                                st.success(msg)
                                                st.rerun()
                                            else:
                                                st.error(msg)
                                        else:
                                            st.error("❌ Por favor, preencha o setor e a data de entrada.")

                                    if submitted_delete_tram:
                                        st.warning(f"Tem certeza que deseja deletar a movimentação ID {dados_tramitacao[0]}?")
                                        confirm_tram_deletion = st.checkbox("Sim, eu confirmo a deleção desta movimentação.", key=f"confirm_checkbox_delete_tram_{tramitacao_selecionada_id}")
                                        if confirm_tram_deletion: 
                                            sucesso, msg = deletar_tramitacao(tramitacao_selecionada_id)
                                            if sucesso:
                                                st.success(msg)
                                                st.rerun()
                                            else:
                                                st.error(msg)

    # ==================== ABA 4: KANBAN ====================
    with tab4:
        st.header("📊 Kanban de Processos")
        processos_kanban = listar()
        if not processos_kanban:
            st.info("📭 Nenhum processo cadastrado para exibir no Kanban.")
        else:
            status_kanban = ["Protocolado", "Em Análise", "Aguardando Correções", "Aprovado", "Reprovado"]
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
                                if sucesso: st.rerun()
                                else: st.error(msg)

                        if current_status_index < len(status_kanban) - 1:
                            if st.button(f"➡️ Mover para {status_kanban[current_status_index+1]}", key=f"move_next_{p[0]}"):
                                sucesso, msg = atualizar_status(p[0], status_kanban[current_status_index+1])
                                if sucesso: st.rerun()
                                else: st.error(msg)
                        st.markdown("---")

    # ==================== ABA 5: ANÁLISE IA ====================
    with tab5:
        st.header("🤖 Análise de Projetos com IA")

        if not st.session_state['api_key']:
            st.warning("⚠️ Configure sua API Key do Google Gemini na barra lateral para usar esta função.")
            st.info("Como obter: Acesse https://aistudio.google.com/app/apikey e crie uma chave gratuita.")
        else:
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
    * Se o projeto parece estar em total conformidade e pronto para aprovação, termine o parecer com a frase **"RECOMENDAÇÃO: PROJETO APROVADO"**.
    * Se o projeto possui pendências ou não conformidades que exigem correção, termine o parecer com a frase **"RECOMENDAÇÃO: PROJETO REPROVADO"**.
    * Se a análise for inconclusiva devido à falta de informações críticas no PDF ou se o PDF for apenas parcial, termine o parecer com a frase **"RECOMENDAÇÃO: ANÁLISE INCONCLUSIVA"**.

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
if not st.session_state['logged_in']:
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

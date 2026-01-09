import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime, date, timedelta # Adicionado timedelta
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
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state: # Adicionado para armazenar o nome de usuário logado
    st.session_state['username'] = None

# ==================== BANCO DE DADOS ====================

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

        # === CORREÇÃO DE NOMES DE SETORES ANTIGOS (se existirem) ===
        # Esta parte foi movida para init_db para ser executada na inicialização
        updates = [
            "UPDATE tramitacao SET setor = 'Pré-análise' WHERE setor = 'Pró-análise'",
            "UPDATE tramitacao SET setor = 'Pré-análise' WHERE setor = 'Pró-Análise'",
            "UPDATE tramitacao SET setor = 'Pré-análise' WHERE setor = 'Pro-analise'",
            "UPDATE tramitacao SET setor = 'Pré-análise' WHERE setor = 'Pro-Analise'"
        ]
        for cmd in updates:
            c.execute(cmd)

        conn.commit()
        return conn
    except Exception as e:
        st.error(f"❌ Erro ao inicializar o banco de dados: {str(e)}")
        return None

conn = init_db()

# ==================== FUNÇÕES AUXILIARES DE BANCO DE DADOS ====================

def executar_query(query, params=(), commit=False):
    """Executa uma query SQL e retorna sucesso/erro e o cursor ou mensagem de erro."""
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        c.execute(query, params)
        if commit: conn.commit()
        return True, c
    except sqlite3.IntegrityError as e:
        return False, f"❌ Erro de integridade: {str(e)}"
    except Exception as e:
        return False, f"❌ Erro no banco de dados: {str(e)}"

def listar_processos():
    """Lista todos os processos cadastrados."""
    suc, res = executar_query('SELECT * FROM processos ORDER BY id DESC')
    return res.fetchall() if suc else []

def buscar_processo(numero_ou_id):
    """Busca um processo pelo número ou ID."""
    query = 'SELECT * FROM processos WHERE id = ?' if isinstance(numero_ou_ou_id, int) else 'SELECT * FROM processos WHERE numero = ?'
    suc, res = executar_query(query, (numero_ou_id,))
    return res.fetchone() if suc else None

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

# ==================== FUNÇÕES CRUD (PROCESSOS) ====================

def cadastrar_processo(numero, rt, requerente, analista, uso, tipologia, area, data_protocolo):
    """Cadastra um novo processo no banco de dados."""
    query = 'INSERT INTO processos (numero, rt, requerente, analista, uso, tipologia, area, data_protocolo) VALUES (?,?,?,?,?,?,?,?)'
    return executar_query(query, (numero, rt, requerente, analista, uso, tipologia, area, data_protocolo), commit=True)

def atualizar_processo(pid, numero, rt, requerente, analista, uso, tipologia, area, data_protocolo):
    """Atualiza os dados de um processo existente."""
    query = 'UPDATE processos SET numero=?, rt=?, requerente=?, analista=?, uso=?, tipologia=?, area=?, data_protocolo=? WHERE id=?'
    return executar_query(query, (numero, rt, requerente, analista, uso, tipologia, area, data_protocolo, pid), commit=True)

def deletar_processo(pid):
    """Deleta um processo e suas tramitações/análises associadas."""
    suc_t, msg_t = executar_query('DELETE FROM tramitacao WHERE processo_id=?', (pid,), commit=True)
    suc_a, msg_a = executar_query('DELETE FROM analises WHERE processo_id=?', (pid,), commit=True)
    suc_p, msg_p = executar_query('DELETE FROM processos WHERE id=?', (pid,), commit=True)

    if suc_p:
        return True, "✅ Processo deletado com sucesso!"
    else:
        return False, f"❌ Erro ao deletar processo: {msg_p}"

def atualizar_status_processo(pid, novo_status):
    """Atualiza o status de um processo."""
    query = 'UPDATE processos SET status=? WHERE id=?'
    return executar_query(query, (novo_status, pid), commit=True)

# ==================== FUNÇÕES CRUD (TRAMITAÇÃO) ====================

def registrar_tramitacao(processo_id, setor, data_entrada, data_saida=None, observacao=""):
    """Registra uma nova movimentação de tramitação para um processo."""
    # Primeiro, fechar qualquer tramitação anterior "em aberto" para este processo
    executar_query("UPDATE tramitacao SET data_saida=? WHERE processo_id=? AND data_saida IS NULL", 
                   (data_entrada.strftime('%Y-%m-%d'), processo_id), commit=True)

    query = "INSERT INTO tramitacao (processo_id, setor, data_entrada, data_saida, observacao) VALUES (?,?,?,?,?)"
    saida_val = data_saida.strftime('%Y-%m-%d') if data_saida else None
    return executar_query(query, (processo_id, setor, data_entrada.strftime('%Y-%m-%d'), saida_val, observacao), commit=True)

def listar_tramitacao(processo_id):
    """Lista as tramitações de um processo específico."""
    suc, res = executar_query('SELECT * FROM tramitacao WHERE processo_id = ? ORDER BY data_entrada DESC', (processo_id,))
    return res.fetchall() if suc else []

def atualizar_tramitacao(tid, setor, data_entrada, data_saida, observacao):
    """Atualiza uma movimentação de tramitação existente."""
    query = "UPDATE tramitacao SET setor=?, data_entrada=?, data_saida=?, observacao=? WHERE id=?"
    saida_val = data_saida.strftime('%Y-%m-%d') if data_saida else None
    return executar_query(query, (setor, data_entrada.strftime('%Y-%m-%d'), saida_val, observacao, tid), commit=True)

def deletar_tramitacao(tid):
    """Deleta uma movimentação de tramitação."""
    query = 'DELETE FROM tramitacao WHERE id = ?'
    return executar_query(query, (tid,), commit=True)

# ==================== FUNÇÕES CRUD (ANÁLISES) ====================

def salvar_analise(processo_id, resultado, status):
    """Salva o resultado de uma análise no banco de dados."""
    query = 'INSERT INTO analises (processo_id, resultado, status) VALUES (?, ?, ?)'
    return executar_query(query, (processo_id, resultado, status), commit=True)

def listar_analises(processo_id):
    """Lista as análises de um processo específico."""
    suc, res = executar_query('SELECT * FROM analises WHERE processo_id = ? ORDER BY data_analise DESC', (processo_id,))
    return res.fetchall() if suc else []

# ==================== INTERFACE PRINCIPAL ====================

def main():
    # --- LOGIN ---
    if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
    if 'username' not in st.session_state: st.session_state['username'] = None

    if not st.session_state['logged_in']:
        st.title("🔐 Login no Sistema de Validação")
        st.markdown("---")
        with st.form("login_form"):
            user_input = st.text_input("Usuário", key="login_username_input")
            pwd_input = st.text_input("Senha", type="password", key="login_password_input")
            submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)

            if submitted:
                admin_user = st.secrets.get("admin_user", {}).get("username")
                admin_pass = st.secrets.get("admin_user", {}).get("password")

                if admin_user is None or admin_pass is None or admin_pass == "SUA_SENHA_REAL_AQUI":
                    st.error("❌ Credenciais de administrador não configuradas corretamente no '.streamlit/secrets.toml'.")
                    st.info("Por favor, verifique se a seção '[admin_user]' com 'username' e 'password' está presente e se a senha não é o placeholder.")
                    return

                if user_input == admin_user and pwd_input == admin_pass:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = user_input
                    st.success(f"Login realizado com sucesso! Bem-vindo(a), {user_input}!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
        st.info("Para acessar o sistema, use o usuário 'admin' e a senha que você configurou no arquivo '.streamlit/secrets.toml'.")
        return # Retorna para não renderizar o resto do app antes do login

    # --- CONTEÚDO PRINCIPAL DO APP APÓS LOGIN ---
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

    # === SEÇÃO DE DADOS E BACKUP ===
    st.sidebar.markdown("---")
    st.sidebar.header("💾 Dados e Backup")
    if conn and pd is not None:
        with st.sidebar.expander("📥 Exportar Planilhas"):
            df_procs = get_processos_df()
            if not df_procs.empty:
                csv_procs = df_procs.to_csv(index=False, sep=';', encoding='utf-8-sig')
                st.download_button("📄 Lista de Processos", csv_procs, "processos.csv", "text/csv")
            try:
                q_hist = "SELECT p.numero, t.* FROM tramitacao t JOIN processos p ON t.processo_id = p.id"
                df_hist = pd.read_sql_query(q_hist, conn)
                if not df_hist.empty:
                    csv_hist = df_hist.to_csv(index=False, sep=';', encoding='utf-8-sig')
                    st.download_button("📜 Histórico Completo", csv_hist, "historico.csv", "text/csv")
            except Exception as e:
                st.sidebar.error(f"Erro ao exportar histórico: {e}")
        if os.path.exists("processos.db"):
            with open("processos.db", "rb") as f:
                st.sidebar.download_button(
                    label="📦 Baixar Backup (.db)",
                    data=f,
                    file_name=f"backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db",
                    mime="application/octet-stream"
                )
        st.sidebar.markdown("---")
        st.sidebar.subheader("⚠️ Restaurar Backup")
        uploaded_db = st.sidebar.file_uploader("Upload do arquivo .db", type="db")
        if uploaded_db:
            st.sidebar.warning("Isso substituirá TODOS os dados. Tem certeza?")
            if st.sidebar.button("🔴 Confirmar Restauração"):
                try:
                    with open("processos.db", "wb") as f:
                        f.write(uploaded_db.getbuffer())
                    st.toast("Restaurado com sucesso! Reiniciando...", icon="✅")
                    import time
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Erro ao restaurar: {e}")

    # --- ABAS ---
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["➕ Cadastrar", "📝 Listar", "🔄 Tramitação", "📊 Kanban", "🤖 Análise IA", "📈 Gráficos"])

    # === LISTAS GLOBAIS (ATUALIZADAS) ===
    usos_options = [
        "Unifamiliar", "Multifamiliar", "Serviços", "Comércio Varejista", 
        "Comércio Atacadista", "Indústria", "Misto", "Sem destinação específica"
    ]
    tipologias_options = [
        "Aprovação Inicial", "Levantamento Existente", "Modificação de Projeto", 
        "Regularização", "Misto", "RIU", "ERB", "As Built"
    ]
    setores_tramitacao = [
        "Protocolo", "Pré-análise", "Analista", "Fiscalização", 
        "Parecer Externo", "Emissão de Alvará", "Requerente", "Arquivo"
    ]
    status_kanban = ["Protocolado", "Em Análise", "Aguardando Correções", "Aprovado", "Reprovado"]

    # --- ABA 1: CADASTRAR ---
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
                analista = st.text_input("Analista Responsável", value=st.session_state.get('username', ''), key="cad_analista") # Preenche com o usuário logado
                tipologia = st.selectbox("Tipologia", tipologias_options, key="cad_tipologia")
                data_protocolo = st.date_input("Data do Protocolo", value="today", key="cad_data_protocolo")

            submitted = st.form_submit_button("Cadastrar Processo", type="primary", use_container_width=True)
            if submitted:
                if numero and rt and requerente and analista and uso and tipologia and area is not None and data_protocolo:
                    suc, msg = cadastrar_processo(numero, rt, requerente, analista, uso, tipologia, area, data_protocolo.strftime('%Y-%m-%d'))
                    if suc:
                        st.success("✅ Processo cadastrado com sucesso!")
                        st.rerun()
                    else:
                        st.error(f"❌ Erro ao cadastrar: {msg}")
                else:
                    st.error("❌ Por favor, preencha todos os campos obrigatórios.")

    # --- ABA 2: LISTAR E GERENCIAR ---
    with tab2:
        st.header("📝 Listar e Gerenciar Processos")
        processos = listar_processos()
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
            col_sel, _ = st.columns([3, 1]) # Usar _ para coluna não utilizada
            with col_sel:
                processo_selecionado_id_num = st.selectbox(
                    "Selecione o Processo pelo ID ou Número:",
                    options=[(p[0], p[1]) for p in processos],
                    format_func=lambda x: f"ID: {x[0]} - Número: {x[1]}",
                    key="select_processo_edit_del"
                )

            if processo_selecionado_id_num:
                pid_selecionado = processo_selecionado_id_num[0]
                st.write(f"DEBUG: Processo selecionado ID para edição/deleção = {pid_selecionado}") # LINHA DE DEBUG
                dados_processo = buscar_processo(processo_selecionado_id_num[1]) # Busca pelo número

                if dados_processo:
                    with st.form(f"edit_processo_{pid_selecionado}"):
                        st.markdown(f"#### Editando Processo ID: {dados_processo[0]} - Número: {dados_processo[1]}")

                        col_e1, col_e2 = st.columns(2)
                        with col_e1:
                            edit_numero = st.text_input("Número do Processo", value=dados_processo[1], key=f"edit_numero_{pid_selecionado}")
                            edit_rt = st.text_input("Responsável Técnico", value=dados_processo[2], key=f"edit_rt_{pid_selecionado}")
                            edit_uso = st.selectbox("Uso", usos_options, index=usos_options.index(dados_processo[5]) if dados_processo[5] in usos_options else 0, key=f"edit_uso_{pid_selecionado}")
                            edit_area = st.number_input("Área Construída (m²)", value=float(dados_processo[7]), min_value=0.0, format="%.2f", key=f"edit_area_{pid_selecionado}")
                        with col_e2:
                            edit_requerente = st.text_input("Requerente", value=dados_processo[3], key=f"edit_requerente_{pid_selecionado}")
                            edit_analista = st.text_input("Analista Responsável", value=dados_processo[4], key=f"edit_analista_{pid_selecionado}")
                            edit_tipologia = st.selectbox("Tipologia", tipologias_options, index=tipologias_options.index(dados_processo[6]) if dados_processo[6] in tipologias_options else 0, key=f"edit_tipologia_{pid_selecionado}")
                            edit_data_protocolo = st.date_input("Data do Protocolo", value=datetime.strptime(dados_processo[8], '%Y-%m-%d').date(), key=f"edit_data_protocolo_{pid_selecionado}")

                        col_upd, col_del = st.columns(2)
                        with col_upd:
                            submitted_update = st.form_submit_button("Atualizar Processo", type="primary", use_container_width=True, key=f"submit_update_{pid_selecionado}")
                        with col_del:
                            submitted_delete = st.form_submit_button("Deletar Processo", type="danger", use_container_width=True, key=f"submit_delete_{pid_selecionado}")

                        if submitted_update:
                            if edit_numero and edit_rt and edit_requerente and edit_analista and edit_uso and edit_tipologia and edit_area is not None and edit_data_protocolo:
                                suc, msg = atualizar_processo(pid_selecionado, edit_numero, edit_rt, edit_requerente, edit_analista, edit_uso, edit_tipologia, edit_area, edit_data_protocolo.strftime('%Y-%m-%d'))
                                if suc:
                                    st.success("✅ Processo atualizado com sucesso!")
                                    st.rerun()
                                else:
                                    st.error(f"❌ Erro ao atualizar: {msg}")
                            else:
                                st.error("❌ Por favor, preencha todos os campos obrigatórios para atualizar.")

                        if submitted_delete:
                            st.warning(f"Tem certeza que deseja deletar o processo {dados_processo[1]}? Todas as tramitações e análises associadas também serão deletadas.")
                            confirm_deletion = st.checkbox("Sim, eu confirmo a deleção deste processo.", key=f"confirm_checkbox_delete_{pid_selecionado}")
                            if confirm_deletion: # A deleção só ocorre se o checkbox for marcado
                                suc, msg = deletar_processo(pid_selecionado)
                                if suc:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)

    # --- ABA 3: TRAMITAÇÃO ---
    with tab3:
        st.header("🔄 Gerenciar Tramitação de Processos")
        processos_tramitacao = listar_processos()
        if not processos_tramitacao:
            st.info("📭 Nenhum processo cadastrado para gerenciar tramitação.")
        else:
            processo_selecionado_tramitacao_id_num = st.selectbox(
                "Selecione o Processo para Tramitação:",
                options=[(p[0], p[1]) for p in processos_tramitacao],
                format_func=lambda x: f"ID: {x[0]} - Número: {x[1]}",
                key="select_processo_tramitacao"
            )

            if processo_selecionado_tramitacao_id_num:
                pid_tramitacao = processo_selecionado_tramitacao_id_num[0]
                st.write(f"DEBUG: Processo selecionado ID para tramitação = {pid_tramitacao}") # LINHA DE DEBUG
                dados_processo_tramitacao = buscar_processo(processo_selecionado_tramitacao_id_num[1]) # Busca pelo número

                if dados_processo_tramitacao:
                    st.subheader(f"Tramitação do Processo: {dados_processo_tramitacao[1]} - Requerente: {dados_processo_tramitacao[3]}")

                    st.markdown("#### Registrar Nova Movimentação")
                    with st.form(f"form_nova_tramitacao_{pid_tramitacao}"):
                        col_t1, col_t2 = st.columns(2)
                        with col_t1:
                            setor = st.selectbox("Setor de Destino", setores_tramitacao, key=f"tram_setor_{pid_tramitacao}")
                            data_entrada = st.date_input("Data de Entrada", value=date.today(), key=f"tram_data_entrada_{pid_tramitacao}")
                        with col_t2:
                            tem_saida = st.checkbox("Informar Data de Saída?", key=f"tram_tem_saida_{pid_tramitacao}")
                            data_saida = None
                            if tem_saida:
                                data_saida = st.date_input("Data de Saída", value=date.today(), key=f"tram_data_saida_{pid_tramitacao}")
                            else:
                                st.caption("Saída 'Em Aberto' (Atual)")
                            observacao = st.text_area("Observação", key=f"tram_obs_{pid_tramitacao}")

                        submitted_tram = st.form_submit_button("Registrar Tramitação", type="primary", use_container_width=True, key=f"submit_tram_{pid_tramitacao}")
                        if submitted_tram:
                            if setor and data_entrada:
                                suc, msg = registrar_tramitacao(pid_tramitacao, setor, data_entrada, data_saida, observacao)
                                if suc:
                                    st.success("✅ Movimentação registrada com sucesso!")
                                    st.rerun()
                                else:
                                    st.error(f"❌ Erro ao registrar tramitação: {msg}")
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
                            options=["Selecione..."] + [t[0] for t in tramitacoes], # Adicionado "Selecione..."
                            format_func=lambda x: f"ID: {x} - Setor: {next((t[2] for t in tramitacoes if t[0] == x), '')}" if x != "Selecione..." else x,
                            key=f"select_tram_edit_del_{pid_tramitacao}"
                        )

                        if tramitacao_selecionada_id != "Selecione...": # Verifica se algo foi selecionado
                            dados_tramitacao = next((t for t in tramitacoes if t[0] == tramitacao_selecionada_id), None)
                            if dados_tramitacao:
                                with st.form(f"form_edit_tramitacao_{tramitacao_selecionada_id}"):
                                    st.markdown(f"##### Editando Movimentação ID: {dados_tramitacao[0]}")
                                    col_et1, col_et2 = st.columns(2)
                                    with col_et1:
                                        edit_setor = st.selectbox("Setor de Destino", setores_tramitacao, index=setores_tramitacao.index(dados_tramitacao[2]) if dados_tramitacao[2] in setores_tramitacao else 0, key=f"edit_tram_setor_{tramitacao_selecionada_id}")
                                        edit_data_entrada = st.date_input("Data de Entrada", value=datetime.strptime(dados_tramitacao[3], '%Y-%m-%d').date(), key=f"edit_tram_data_entrada_{tramitacao_selecionada_id}")
                                    with col_et2:
                                        edit_tem_saida = st.checkbox("Informar Data de Saída?", value=bool(dados_tramitacao[4]), key=f"edit_tram_tem_saida_{tramitacao_selecionada_id}")
                                        edit_data_saida = None
                                        if edit_tem_saida:
                                            edit_data_saida_val = datetime.strptime(dados_tramitacao[4], '%Y-%m-%d').date() if dados_tramitacao[4] else date.today()
                                            edit_data_saida = st.date_input("Data de Saída", value=edit_data_saida_val, key=f"edit_tram_data_saida_{tramitacao_selecionada_id}")
                                        edit_observacao = st.text_area("Observação", value=dados_tramitacao[5] or "", key=f"edit_tram_obs_{tramitacao_selecionada_id}")

                                    col_upd_tram, col_del_tram = st.columns(2)
                                    with col_upd_tram:
                                        submitted_update_tram = st.form_submit_button("Atualizar Movimentação", type="primary", use_container_width=True, key=f"submit_update_tram_{tramitacao_selecionada_id}")
                                    with col_del_tram:
                                        submitted_delete_tram = st.form_submit_button("Deletar Movimentação", type="danger", use_container_width=True, key=f"submit_delete_tram_{tramitacao_selecionada_id}")

                                    if submitted_update_tram:
                                        if edit_setor and edit_data_entrada:
                                            suc, msg = atualizar_tramitacao(tramitacao_selecionada_id, edit_setor, edit_data_entrada, edit_data_saida, edit_observacao)
                                            if suc:
                                                st.success("✅ Movimentação atualizada!")
                                                st.rerun()
                                            else:
                                                st.error(f"❌ Erro ao atualizar movimentação: {msg}")
                                        else:
                                            st.error("❌ Por favor, preencha o setor e a data de entrada.")

                                    if submitted_delete_tram:
                                        st.warning(f"Tem certeza que deseja deletar a movimentação ID {dados_tramitacao[0]}?")
                                        confirm_tram_deletion = st.checkbox("Sim, eu confirmo a deleção desta movimentação.", key=f"confirm_checkbox_delete_tram_{tramitacao_selecionada_id}")
                                        if confirm_tram_deletion: # A deleção só ocorre se o checkbox for marcado
                                            suc, msg = deletar_tramitacao(tramitacao_selecionada_id)
                                            if suc:
                                                st.success("✅ Movimentação deletada!")
                                                st.rerun()
                                            else:
                                                st.error(f"❌ Erro ao deletar movimentação: {msg}")

    # --- ABA 4: KANBAN ---
    with tab4:
        st.header("📊 Kanban de Processos")
        processos_kanban = listar_processos()
        if not processos_kanban:
            st.info("📭 Nenhum processo cadastrado para exibir no Kanban.")
        else:
            cols = st.columns(len(status_kanban))

            for i, status in enumerate(status_kanban):
                with cols[i]:
                    st.subheader(f"{status} ({len([p for p in processos_kanban if p[9] == status])})") # Contagem dinâmica
                    st.markdown("---")

                    for p in [x for x in processos_kanban if x[9] == status]:
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
                                suc, msg = atualizar_status_processo(p[0], status_kanban[current_status_index-1])
                                if suc: st.rerun()
                                else: st.error(f"Erro ao mover: {msg}")

                        if current_status_index < len(status_kanban) - 1:
                            if st.button(f"➡️ Mover para {status_kanban[current_status_index+1]}", key=f"move_next_{p[0]}"):
                                suc, msg = atualizar_status_processo(p[0], status_kanban[current_status_index+1])
                                if suc: st.rerun()
                                else: st.error(f"Erro ao mover: {msg}")
                        st.markdown("---")

    # --- ABA 5: ANÁLISE IA ---
    with tab5:
        st.header("🤖 Análise de Projetos com IA")

        if not st.session_state['api_key']:
            st.warning("⚠️ Configure sua API Key do Google Gemini na barra lateral para usar esta função.")
            st.info("Como obter: Acesse https://aistudio.google.com/app/apikey e crie uma chave gratuita.")
            st.stop()

        processos_analise = listar_processos()
        if not processos_analise:
            st.info("📭 Nenhum processo cadastrado para análise.")
        else:
            processo_selecionado_analise_id_num = st.selectbox(
                "Selecione o Processo para Análise:",
                options=[(p[0], p[1]) for p in processos_analise],
                format_func=lambda x: f"ID: {x[0]} - Número: {x[1]}",
                key="select_processo_analise"
            )

            if processo_selecionado_analise_id_num:
                pid_analise = processo_selecionado_analise_id_num[0]
                st.write(f"DEBUG: Processo selecionado ID para análise IA = {pid_analise}") # LINHA DE DEBUG
                dados = buscar_processo(processo_selecionado_analise_id_num[1]) # Busca pelo número

                if dados:
                    st.subheader(f"Analisando Processo: {dados[1]} - Requerente: {dados[3]}")
                    st.markdown(f"**Status Atual:** {dados[9]}")

                    st.divider()
                    st.markdown("#### 📄 Anexar Documentos")
                    col_proj, col_leg = st.columns(2)
                    with col_proj:
                        proj = st.file_uploader("🏗️ Projeto Arquitetônico (PDF)", type=['pdf'], accept_multiple_files=True, key="proj_upload")
                    with col_leg:
                        leg = st.file_uploader("📜 Legislação Municipal (PDF)", type=['pdf'], accept_multiple_files=True, key="leg_upload")

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
                                    modelos_disponiveis = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']
                                    for nome in modelos_disponiveis:
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
- **Regras Específicas a Verificar:** {regras}

Com base no texto do projeto e nas informações acima, forneça um parecer técnico detalhado.
O parecer deve incluir:
1.  **Resumo do Projeto:** Uma breve descrição do que o projeto propõe.
2.  **Conformidade:** Pontos em que o projeto parece estar em conformidade com normas gerais de construção e urbanismo (ex: recuos, taxa de ocupação, coeficiente de aproveitamento, ventilação, iluminação, acessibilidade, etc.) E COM AS REGRAS ESPECÍFICAS FORNECIDAS.
3.  **Não Conformidade/Pendências:** Pontos que precisam de correção ou esclarecimento para a aprovação. Seja específico sobre quais itens estão em desacordo ou quais informações estão faltando.
4.  **Recomendação Final:**
    *   Se o projeto parece estar em total conformidade e pronto para aprovação, termine o parecer com a frase **"RECOMENDAÇÃO: PROJETO APROVADO"**.
    *   Se o projeto possui pendências ou não conformidades que exigem correção, termine o parecer com a frase **"RECOMENDAÇÃO: PROJETO REPROVADO"**.
    *   Se a análise for inconclusiva devido à falta de informações críticas no PDF ou se o PDF for apenas parcial, termine o parecer com a frase **"RECOMENDAÇÃO: ANÁLISE INCONCLUSIVA"**.

---
**TEXTO DO PROJETO ARQUITETÔNICO:**
{txt_proj[:15000]} # Limita o texto para evitar estouro de token
---
**TEXTO DA LEGISLAÇÃO MUNICIPAL (para referência):**
{txt_leg[:15000]} # Limita o texto para evitar estouro de token
---
"""

                                    resposta = model.generate_content(prompt)

                                    texto_resposta = resposta.text

                                    status_analise = "INCONCLUSIVO"
                                    if "APROVADO" in texto_resposta.upper() and "REPROVADO" not in texto_resposta.upper():
                                        status_analise = "Aprovado"
                                        st.success("✅ PROJETO APROVADO")
                                        atualizar_status_processo(dados[0], "Aprovado")
                                    elif "REPROVADO" in texto_resposta.upper():
                                        status_analise = "Reprovado"
                                        st.error("❌ PROJETO REPROVADO")
                                        atualizar_status_processo(dados[0], "Reprovado")
                                    else:
                                        status_analise = "Em Análise" # Mantém em análise se inconclusivo
                                        st.warning("⚠️ ANÁLISE INCONCLUSIVA")
                                        atualizar_status_processo(dados[0], "Em Análise")

                                    st.divider()

                                    st.markdown(resposta.text)

                                    suc_analise, msg_analise = salvar_analise(dados[0], resposta.text, status_analise)
                                    if not suc_analise:
                                        st.error(f"❌ Erro ao salvar análise no banco de dados: {msg_analise}")

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

    # --- ABA 6: GRÁFICOS (DASHBOARD) ---
    with tab6:
        st.header("📈 Análise Gráfica dos Processos")

        if pd is None or px is None:
            st.error("❌ As bibliotecas de gráficos (pandas, plotly) não estão disponíveis. Verifique seu 'requirements.txt'.")
        else:
            procs_df = get_processos_df()

            if procs_df.empty:
                st.info("📭 Nenhum dado para gerar gráficos. Cadastre processos primeiro na aba 'Cadastrar'.")
            else:
                # Métricas
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                col_m1.metric("Total de Processos", len(procs_df))
                col_m2.metric("Área Total Construída", f"{procs_df['area'].sum():,.0f} m²")
                col_m3.metric("Processos Aprovados", len(procs_df[procs_df['status']=='Aprovado']))

                # Calcular tempo médio de tramitação
                df_tram_all_for_metrics = pd.read_sql_query("SELECT processo_id, data_entrada, data_saida FROM tramitacao", conn)
                if not df_tram_all_for_metrics.empty:
                    df_tram_all_for_metrics['data_entrada'] = pd.to_datetime(df_tram_all_for_metrics['data_entrada'])
                    df_tram_all_for_metrics['data_saida'] = pd.to_datetime(df_tram_all_for_metrics['data_saida'])
                    df_tram_all_for_metrics['duracao_total'] = (df_tram_all_for_metrics['data_saida'] - df_tram_all_for_metrics['data_entrada']).dt.days

                    # Filtrar apenas tramitações concluídas para média
                    df_concluidas = df_tram_all_for_metrics.dropna(subset=['duracao_total'])
                    if not df_concluidas.empty:
                        media_dias_tramitacao = df_concluidas.groupby('processo_id')['duracao_total'].sum().mean()
                        col_m4.metric("Média Dias Tramitação", f"{media_dias_tramitacao:.0f} dias")
                    else:
                        col_m4.metric("Média Dias Tramitação", "N/A")
                else:
                    col_m4.metric("Média Dias Tramitação", "N/A")

                st.divider()

                st.subheader("Selecione o tipo de gráfico para visualizar os dados:")
                chart_type = st.selectbox("Escolha a análise:", [
                    "Processos por Status",
                    "Processos por Uso",
                    "Processos por Tipologia",
                    "Processos por Analista",
                    "Área Total por Uso",
                    "Processos por Data de Protocolo",
                    "Tempo Médio por Setor (Tramitação)"
                ])

                st.divider()

                if chart_type == "Processos por Status":
                    st.markdown("### 📊 Distribuição de Processos por Status")
                    df_grouped = procs_df['status'].value_counts().reset_index()
                    df_grouped.columns = ['Status', 'Quantidade']
                    fig = px.pie(df_grouped, values='Quantidade', names='Status', 
                                 title='Distribuição Percentual de Processos por Status',
                                 hole=0.3, 
                                 template='plotly_white')
                    st.plotly_chart(fig, use_container_width=True)

                elif chart_type == "Processos por Uso":
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

                elif chart_type == "Tempo Médio por Setor (Tramitação)":
                    st.markdown("### 📊 Tempo Médio de Permanência por Setor na Tramitação")
                    df_tram_all = pd.read_sql_query("SELECT * FROM tramitacao", conn)
                    if not df_tram_all.empty:
                        df_tram_all['data_entrada'] = pd.to_datetime(df_tram_all['data_entrada'])
                        df_tram_all['data_saida'] = pd.to_datetime(df_tram_all['data_saida'])
                        now = pd.Timestamp.now().normalize()
                        df_tram_all['data_saida_calculo'] = df_tram_all['data_saida'].fillna(now) # Usar 'now' para tramitações em aberto
                        df_tram_all['dias'] = (df_tram_all['data_saida_calculo'] - df_tram_all['data_entrada']).dt.days

                        df_setor_medio = df_tram_all.groupby('setor')['dias'].mean().reset_index()
                        df_setor_medio = df_setor_medio.sort_values('dias', ascending=False)

                        fig = px.bar(df_setor_medio, x='dias', y='setor', orientation='h',
                                     title='Tempo Médio (Dias) por Setor',
                                     labels={'dias': 'Média de Dias', 'setor': 'Setor'},
                                     text_auto='.0f',
                                     template='plotly_white')
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("Nenhum dado de tramitação para este gráfico.")

if __name__ == "__main__":
    main()

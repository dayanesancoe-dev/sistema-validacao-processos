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
    st.error("❌ Erro: As bibliotecas 'pandas' e 'plotly' não foram encontradas. A aba de gráficos não funcionará.")

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
        return False, "❌ Erro: Já existe um processo com este número."
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
        return False, "❌ Erro: Número de processo já existe!"
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
        st.error(f"❌ Erro ao carregar processos: {e}")
        return pd.DataFrame()

# ==================== LOGIN ====================

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
                st.error("❌ Credenciais não configuradas no '.streamlit/secrets.toml'.")
                return

            if username == admin_username and password == admin_password:
                st.session_state['logged_in'] = True
                st.session_state['username'] = username
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")

# ==================== APP PRINCIPAL ====================

def main_app_content():
    usos_options = ["Unifamiliar", "Multifamiliar", "Serviços", "Comércio Varejista", "Comércio Atacadista", "Indústria", "Misto", "Sem destinação específica"]
    tipologias_options = ["Aprovação Inicial", "Levantamento Existente", "Modificação de Projeto", "Regularização", "Misto", "RIU", "ERB", "As Built"]
    status_kanban = ["Protocolado", "Em Análise", "Aguardando Correções", "Aprovado", "Reprovado"]

    st.sidebar.title("🏛️ Sistema de Validação")
    st.sidebar.markdown(f"Bem-vindo(a), **{st.session_state.get('username', 'Usuário')}**!")
    
    if st.sidebar.button("Sair", type="secondary", key="logout"): 
        st.session_state['logged_in'] = False
        st.rerun()

    st.sidebar.markdown("---")
    st.session_state['api_key'] = st.sidebar.text_input("Sua API Key Gemini:", type="password", key="sidebar_api_key")
    if st.session_state['api_key']:
        genai.configure(api_key=st.session_state['api_key'])

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["➕ Cadastrar", "📝 Listar", "🔄 Tramitação", "📊 Kanban", "🤖 Análise IA", "📈 Gráficos"])

    # --- ABA 1: CADASTRAR ---
    with tab1:
        st.header("➕ Cadastrar Processo")
        with st.form("cadastro"):
            col1, col2 = st.columns(2)
            with col1:
                numero = st.text_input("Número do Processo")
                rt = st.text_input("Responsável Técnico")
                uso = st.selectbox("Uso", usos_options)
                area = st.number_input("Área (m²)", min_value=0.0, format="%.2f")
            with col2:
                requerente = st.text_input("Requerente")
                analista = st.text_input("Analista")
                tipologia = st.selectbox("Tipologia", tipologias_options)
                data_protocolo = st.date_input("Data Protocolo", value="today")

            if st.form_submit_button("Cadastrar", type="primary", use_container_width=True):
                if numero and rt and requerente:
                    suc, msg = cadastrar(numero, rt, requerente, analista, uso, tipologia, area, data_protocolo.strftime('%Y-%m-%d'))
                    if suc: st.success(msg); st.rerun()
                    else: st.error(msg)
                else:
                    st.error("Preencha os campos obrigatórios.")

    # --- ABA 2: LISTAR (SIMPLIFICADA) ---
    with tab2:
        st.header("📝 Gerenciar Processos")
        processos = listar()
        if processos:
            df = pd.DataFrame(processos, columns=["ID", "Número", "RT", "Requerente", "Analista", "Uso", "Tipologia", "Área", "Data", "Status", "Cadastro"])
            st.dataframe(df, use_container_width=True)
            
            sel_proc = st.selectbox("Selecione para Editar/Deletar:", [(p[0], p[1]) for p in processos], format_func=lambda x: f"{x[1]}", key="sel_edit")
            
            if sel_proc:
                pid = sel_proc[0]
                d = buscar_por_numero(sel_proc[1])
                if d:
                    # FORMULÁRIO SIMPLIFICADO (SEM COLUNAS INTERNAS) PARA EVITAR ERRO
                    with st.form(f"form_edit_{pid}"):
                        st.subheader(f"Editando: {d[1]}")
                        e_num = st.text_input("Número", value=d[1])
                        e_rt = st.text_input("RT", value=d[2])
                        e_req = st.text_input("Requerente", value=d[3])
                        e_ana = st.text_input("Analista", value=d[4])
                        e_uso = st.selectbox("Uso", usos_options, index=usos_options.index(d[5]) if d[5] in usos_options else 0)
                        e_tipo = st.selectbox("Tipologia", tipologias_options, index=tipologias_options.index(d[6]) if d[6] in tipologias_options else 0)
                        e_area = st.number_input("Área", value=float(d[7]))
                        e_data = st.date_input("Data", value=datetime.strptime(d[8], '%Y-%m-%d').date())
                        
                        st.markdown("---")
                        # Botões diretamente dentro do form (sem colunas)
                        btn_upd = st.form_submit_button("Atualizar Dados", type="primary", use_container_width=True)
                        btn_del = st.form_submit_button("Deletar Processo", type="danger", use_container_width=True)

                    if btn_upd:
                        suc, msg = atualizar(pid, e_num, e_rt, e_req, e_ana, e_uso, e_tipo, e_area, e_data.strftime('%Y-%m-%d'))
                        if suc: st.success(msg); st.rerun()
                        else: st.error(msg)
                    
                    if btn_del:
                        st.warning("Confirma deleção?")
                        if st.checkbox("Sim, deletar"):
                            suc, msg = deletar(pid)
                            if suc: st.success(msg); st.rerun()
                            else: st.error(msg)

    # --- ABA 3: TRAMITAÇÃO ---
    with tab3:
        st.header("🔄 Tramitação")
        processos = listar()
        if processos:
            sel_tram = st.selectbox("Selecione o Processo:", [(p[0], p[1]) for p in processos], format_func=lambda x: f"{x[1]}", key="sel_tram")
            if sel_tram:
                pid = sel_tram[0]
                with st.form(f"nova_tram_{pid}"):
                    st.subheader("Nova Movimentação")
                    col1, col2 = st.columns(2)
                    with col1:
                        t_setor = st.text_input("Setor")
                        t_ent = st.date_input("Entrada", value="today")
                    with col2:
                        t_sai = st.date_input("Saída", value=None)
                        t_obs = st.text_area("Obs")
                    if st.form_submit_button("Registrar"):
                        suc, msg = registrar_tramitacao(pid, t_setor, t_ent, t_sai, t_obs)
                        if suc: st.success(msg); st.rerun()
                        else: st.error(msg)
                
                trams = listar_tramitacao(pid)
                if trams:
                    df_t = pd.DataFrame(trams, columns=["ID", "PID", "Setor", "Entrada", "Saída", "Obs"])
                    st.dataframe(df_t)

    # --- ABA 4: KANBAN ---
    with tab4:
        st.header("📊 Kanban")
        processos = listar()
        if processos:
            cols = st.columns(5)
            for i, status in enumerate(status_kanban):
                with cols[i]:
                    st.caption(f"**{status}**")
                    procs_status = [p for p in processos if p[9] == status]
                    for p in procs_status:
                        with st.container(border=True):
                            st.markdown(f"**{p[1]}**\n\n{p[3]}")
                            if i > 0:
                                if st.button("⬅️", key=f"prev_{p[0]}"):
                                    atualizar_status(p[0], status_kanban[i-1]); st.rerun()
                            if i < 4:
                                if st.button("➡️", key=f"next_{p[0]}"):
                                    atualizar_status(p[0], status_kanban[i+1]); st.rerun()

    # --- ABA 5: IA ---
    with tab5:
        st.header("🤖 Análise IA")
        if not st.session_state['api_key']:
            st.warning("Insira a API Key na barra lateral.")
        else:
            processos = listar()
            if processos:
                sel_ia = st.selectbox("Processo:", [(p[0], p[1]) for p in processos], format_func=lambda x: f"{x[1]}", key="sel_ia")
                if sel_ia:
                    pid = sel_ia[0]
                    d = buscar_por_numero(sel_ia[1])
                    proj = st.file_uploader("PDF Projeto", type=['pdf'], accept_multiple_files=True)
                    leg = st.file_uploader("PDF Lei", type=['pdf'], accept_multiple_files=True)
                    regras = st.text_area("Regras a verificar:")
                    
                    if st.button("Analisar com IA", type="primary"):
                        if proj and leg and regras:
                            with st.spinner("Analisando..."):
                                try:
                                    txt_p = ""
                                    for p in proj: txt_p += PyPDF2.PdfReader(p).pages[0].extract_text()
                                    txt_l = ""
                                    for l in leg: txt_l += PyPDF2.PdfReader(l).pages[0].extract_text()
                                    
                                    model = genai.GenerativeModel('gemini-1.5-flash')
                                    prompt = f"Analise o projeto {d[1]} ({d[5]}, {d[7]}m²) com base na lei:\n\nLEI: {txt_l[:5000]}\n\nPROJETO: {txt_p[:5000]}\n\nREGRAS: {regras}"
                                    resp = model.generate_content(prompt)
                                    st.markdown(resp.text)
                                    salvar_analise(pid, resp.text, "Concluído")
                                except Exception as e:
                                    st.error(f"Erro: {e}")

    # --- ABA 6: GRÁFICOS ---
    with tab6:
        st.header("📈 Gráficos")
        if pd and px:
            df = get_processos_df()
            if not df.empty:
                grafico = st.selectbox("Tipo", ["Por Uso", "Por Status"])
                if grafico == "Por Uso":
                    fig = px.bar(df['uso'].value_counts().reset_index(), x='uso', y='count')
                    st.plotly_chart(fig)
                elif grafico == "Por Status":
                    fig = px.pie(df['status'].value_counts().reset_index(), names='status', values='count')
                    st.plotly_chart(fig)

if not st.session_state['logged_in']:
    login_form()
else:
    main_app_content()

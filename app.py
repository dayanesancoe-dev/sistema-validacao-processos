import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime, timedelta
import sqlite3
import os
# Removido bcrypt e qualquer lógica de autenticação

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
# Removido 'logged_in' e 'username' pois não haverá login
# if 'logged_in' not in st.session_state:
#     st.session_state['logged_in'] = False
# if 'username' not in st.session_state:
#     st.session_state['username'] = None

if st.session_state['db_reset_needed_rerun']:
    st.session_state['db_reset_needed_rerun'] = False
    st.rerun()

# ==================== BANCO DE DADOS ====================

# A função reset_database foi removida para simplificar e evitar o erro persistente.
# Se precisar resetar o banco, você terá que deletar o arquivo 'processos.db' manualmente no ambiente do Streamlit Share
# (se tiver acesso aos arquivos) ou recriar o app.

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
            # Removido 'DROP TABLE IF EXISTS users' pois a tabela de usuários não será mais usada
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

        # Removida a criação da tabela 'users'

        conn.commit()
        return conn
    except Exception as e:
        st.error(f"❌ Erro ao inicializar o banco de dados: {str(e)}")
        return None

conn = init_db()

# ==================== FUNÇÕES CRUD (PROCESSOS) ====================

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
        # Atualiza a data de saída da última tramitação aberta para este processo
        c.execute('''UPDATE tramitacao 
                    SET data_saida = ? 
                    WHERE processo_id = ? AND data_saida IS NULL''', 
                 (data_entrada.strftime('%Y-%m-%d'), processo_id)) # Formata data_entrada para string

        # Insere a nova tramitação
        c.execute('''INSERT INTO tramitacao 
                    (processo_id, setor, data_entrada, data_saida, observacao) 
                    VALUES (?, ?, ?, ?, ?)''',
                 (processo_id, setor, data_entrada.strftime('%Y-%m-%d'), data_saida.strftime('%Y-%m-%d') if data_saida else None, observacao))
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
        return True, "✅ Movimentação atualizada!"
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
    """Salva o resultado de uma análise de IA para um processo."""
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        c.execute('''INSERT INTO analises (processo_id, resultado, status) VALUES (?, ?, ?)''',
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

# ==================== LAYOUT DO APP ====================

def main_app_content():
    """Conteúdo principal do aplicativo após o login."""
    st.sidebar.title("🏛️ Sistema de Validação")
    st.sidebar.markdown(f"Bem-vindo(a), **Usuário**!") # Removido st.session_state['username']
    st.sidebar.image("https://www.contagem.mg.gov.br/portal/uploads/2023/07/logo-contagem-2023.png", width=200)
    st.sidebar.markdown("---")

    # Removido o botão "Sair" pois não há login
    # st.sidebar.button("Sair", type="secondary", key="sidebar_logout_button")

    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Configurações")
    api_key_input = st.sidebar.text_input("🔑 Sua API Key do Google Gemini:", type="password", key="api_key_sidebar")
    if api_key_input:
        st.session_state['api_key'] = api_key_input
        st.sidebar.success("API Key configurada!")
    else:
        st.session_state['api_key'] = ''
        st.sidebar.warning("Por favor, insira sua API Key do Google Gemini na barra lateral.")

    # Removido o botão "Resetar Banco de Dados" e a função reset_database

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "➕ Cadastrar", "📝 Listar", "🔄 Tramitação", "🔍 Análise IA", "📊 Gráficos", "⚙️ Configurações DB"
    ])

    with tab1:
        st.header("➕ Cadastrar Novo Processo")
        with st.form("cadastro_processo", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                numero = st.text_input("Número do Processo:", help="Ex: 123456/2023", key="num_proc_cad")
                rt = st.text_input("Responsável Técnico:", key="rt_cad")
                analista = st.text_input("Analista Responsável:", key="analista_cad")

                # Opções de Uso (Memória do Usuário)
                uso_options = ["Multifamiliar", "Serviços", "Comércio Varejista", "Comércio Atacadista", 
                               "Indústria", "Unifamiliar", "Misto", "Sem Destinação Específica"]
                uso = st.selectbox("Uso Predominante:", options=uso_options, key="uso_cad")

                area = st.number_input("Área Construída (m²):", min_value=0.0, format="%.2f", key="area_cad")
            with col2:
                requerente = st.text_input("Requerente:", key="req_cad")

                # Opções de Tipologia (Memória do Usuário)
                tipologia_options = ["Aprovação Inicial", "Levantamento Existente", "Modificação de Projeto", 
                                     "Regularização", "Misto", "RIU", "ERB", "As Built"]
                tipologia = st.selectbox("Tipologia do Projeto:", options=tipologia_options, key="tip_cad")

                data_protocolo = st.date_input("Data do Protocolo:", key="data_prot_cad")

            st.divider()
            submitted = st.form_submit_button("✅ Cadastrar Processo", type="primary", use_container_width=True)

            if submitted:
                if numero and rt and requerente and analista and uso and tipologia and area is not None and data_protocolo:
                    data_protocolo_str = data_protocolo.strftime('%Y-%m-%d')
                    success, message = cadastrar(numero, rt, requerente, analista, uso, tipologia, area, data_protocolo_str)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.error("❌ Por favor, preencha todos os campos obrigatórios.")

    with tab2:
        st.header("📝 Listar e Gerenciar Processos")
        processos = listar()
        if not processos:
            st.info("📭 Nenhum processo cadastrado ainda.")
        else:
            df_processos = pd.DataFrame(processos, columns=[
                'ID', 'Número', 'RT', 'Requerente', 'Analista', 'Uso', 
                'Tipologia', 'Área (m²)', 'Data Protocolo', 'Status', 'Data Cadastro'
            ])

            st.dataframe(df_processos, use_container_width=True)

            st.divider()
            st.subheader("Editar ou Deletar Processo")

            col_edit_del, col_status = st.columns(2)

            with col_edit_del:
                processo_selecionado_id = st.selectbox(
                    "Selecione o ID do Processo:",
                    options=[p[0] for p in processos],
                    format_func=lambda x: f"{buscar_por_id(x)[1]} - {buscar_por_id(x)[3]}",
                    key="select_proc_edit_del"
                )

                if processo_selecionado_id:
                    dados_proc = buscar_por_id(processo_selecionado_id)
                    if dados_proc:
                        with st.form("editar_deletar_processo", clear_on_submit=False):
                            st.markdown(f"**Editando Processo ID:** `{dados_proc[0]}` - **Número:** `{dados_proc[1]}`")

                            edit_numero = st.text_input("Número do Processo:", value=dados_proc[1], key="edit_num_proc")
                            edit_rt = st.text_input("Responsável Técnico:", value=dados_proc[2], key="edit_rt")
                            edit_requerente = st.text_input("Requerente:", value=dados_proc[3], key="edit_req")
                            edit_analista = st.text_input("Analista Responsável:", value=dados_proc[4], key="edit_analista")

                            edit_uso = st.selectbox("Uso Predominante:", options=uso_options, index=uso_options.index(dados_proc[5]), key="edit_uso")
                            edit_tipologia = st.selectbox("Tipologia do Projeto:", options=tipologia_options, index=tipologia_options.index(dados_proc[6]), key="edit_tip")

                            edit_area = st.number_input("Área Construída (m²):", value=float(dados_proc[7]), min_value=0.0, format="%.2f", key="edit_area")
                            edit_data_protocolo = st.date_input("Data do Protocolo:", value=datetime.strptime(dados_proc[8], '%Y-%m-%d').date(), key="edit_data_prot")

                            col_btns_edit_del = st.columns(2)
                            with col_btns_edit_del[0]:
                                submitted_edit = st.form_submit_button("✏️ Atualizar Processo", type="primary", use_container_width=True)
                            with col_btns_edit_del[1]:
                                submitted_delete = st.form_submit_button("🗑️ Deletar Processo", type="danger", use_container_width=True)

                            if submitted_edit:
                                if edit_numero and edit_rt and edit_requerente and edit_analista and edit_uso and edit_tipologia and edit_area is not None and edit_data_protocolo:
                                    edit_data_protocolo_str = edit_data_protocolo.strftime('%Y-%m-%d')
                                    success, message = atualizar(processo_selecionado_id, edit_numero, edit_rt, edit_requerente, edit_analista, edit_uso, edit_tipologia, edit_area, edit_data_protocolo_str)
                                    if success:
                                        st.success(message)
                                        st.rerun()
                                    else:
                                        st.error(message)
                                else:
                                    st.error("❌ Por favor, preencha todos os campos para atualizar.")

                            if submitted_delete:
                                if st.warning(f"Tem certeza que deseja deletar o processo {dados_proc[1]}? Esta ação é irreversível."):
                                    if st.button("CONFIRMAR DELETAR", key="confirm_delete_proc", type="danger"):
                                        success, message = deletar(processo_selecionado_id)
                                        if success:
                                            st.success(message)
                                            st.rerun()
                                        else:
                                            st.error(message)

            with col_status:
                st.subheader("Atualizar Status Kanban")
                processo_status_id = st.selectbox(
                    "Selecione o ID do Processo para Status:",
                    options=[p[0] for p in processos],
                    format_func=lambda x: f"{buscar_por_id(x)[1]} - {buscar_por_id(x)[3]}",
                    key="select_proc_status"
                )

                if processo_status_id:
                    dados_status = buscar_por_id(processo_status_id)
                    if dados_status:
                        st.info(f"Status atual: **{dados_status[9]}**")
                        novo_status = st.selectbox(
                            "Novo Status:",
                            options=["Protocolado", "Em Análise", "Aprovado", "Reprovado", "Arquivado"],
                            index=["Protocolado", "Em Análise", "Aprovado", "Reprovado", "Arquivado"].index(dados_status[9]),
                            key="novo_status_select"
                        )
                        if st.button("🔄 Atualizar Status", type="secondary", use_container_width=True, key="btn_update_status"):
                            success, message = atualizar_status(processo_status_id, novo_status)
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)

    with tab3:
        st.header("🔄 Gerenciar Tramitação de Processos")
        processos_tramitacao = listar()
        if not processos_tramitacao:
            st.info("📭 Nenhum processo cadastrado para tramitação.")
        else:
            processo_selecionado_tramitacao = st.selectbox(
                "Selecione o Processo para Tramitação:",
                options=[(p[0], p[1]) for p in processos_tramitacao],
                format_func=lambda x: f"{x[1]} - {buscar_por_numero(x[1])[3]}",
                key="select_processo_tramitacao"
            )

            if processo_selecionado_tramitacao:
                pid_tramitacao = processo_selecionado_tramitacao[0]
                st.subheader(f"Tramitação do Processo: {processo_selecionado_tramitacao[1]}")

                tramitacoes = listar_tramitacao(pid_tramitacao)
                if tramitacoes:
                    df_tramitacoes = pd.DataFrame(tramitacoes, columns=[
                        'ID', 'Processo ID', 'Setor', 'Data Entrada', 'Data Saída', 'Observação'
                    ])
                    st.dataframe(df_tramitacoes, use_container_width=True)
                else:
                    st.info("📭 Nenhuma tramitação registrada para este processo.")

                st.divider()
                st.subheader("Registrar Nova Tramitação")
                with st.form("nova_tramitacao", clear_on_submit=True):
                    col_tram_1, col_tram_2 = st.columns(2)
                    with col_tram_1:
                        setor = st.text_input("Setor de Destino:", key="setor_tram")
                        data_entrada = st.date_input("Data de Entrada:", key="data_entrada_tram")
                    with col_tram_2:
                        data_saida = st.date_input("Data de Saída (opcional):", value=None, key="data_saida_tram")
                        observacao = st.text_area("Observação:", key="obs_tram")

                    submitted_tram = st.form_submit_button("➕ Registrar Tramitação", type="primary", use_container_width=True)

                    if submitted_tram:
                        if setor and data_entrada:
                            success, message = registrar_tramitacao(pid_tramitacao, setor, data_entrada, data_saida, observacao)
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
                        else:
                            st.error("❌ Por favor, preencha o setor e a data de entrada.")

                st.divider()
                st.subheader("Editar/Deletar Tramitação Existente")
                if tramitacoes:
                    tramitacao_selecionada_id = st.selectbox(
                        "Selecione a Tramitação para Editar/Deletar:",
                        options=[t[0] for t in tramitacoes],
                        format_func=lambda x: f"ID {x} - {buscar_tramitacao_por_id(x)[2]} ({buscar_tramitacao_por_id(x)[3]})",
                        key="select_tram_edit_del"
                    )

                    if tramitacao_selecionada_id:
                        dados_tram = buscar_tramitacao_por_id(tramitacao_selecionada_id)
                        if dados_tram:
                            with st.form("editar_deletar_tramitacao", clear_on_submit=False):
                                st.markdown(f"**Editando Tramitação ID:** `{dados_tram[0]}` - **Setor:** `{dados_tram[2]}`")

                                edit_setor = st.text_input("Setor:", value=dados_tram[2], key="edit_setor_tram")
                                edit_data_entrada = st.date_input("Data de Entrada:", value=datetime.strptime(dados_tram[3], '%Y-%m-%d').date(), key="edit_data_entrada_tram")
                                edit_data_saida_val = datetime.strptime(dados_tram[4], '%Y-%m-%d').date() if dados_tram[4] else None
                                edit_data_saida = st.date_input("Data de Saída:", value=edit_data_saida_val, key="edit_data_saida_tram")
                                edit_observacao = st.text_area("Observação:", value=dados_tram[5], key="edit_obs_tram")

                                col_btns_tram_edit_del = st.columns(2)
                                with col_btns_tram_edit_del[0]:
                                    submitted_edit_tram = st.form_submit_button("✏️ Atualizar Tramitação", type="primary", use_container_width=True)
                                with col_btns_tram_edit_del[1]:
                                    submitted_delete_tram = st.form_submit_button("🗑️ Deletar Tramitação", type="danger", use_container_width=True)

                                if submitted_edit_tram:
                                    if edit_setor and edit_data_entrada:
                                        success, message = atualizar_tramitacao(tramitacao_selecionada_id, edit_setor, edit_data_entrada.strftime('%Y-%m-%d'), edit_data_saida.strftime('%Y-%m-%d') if edit_data_saida else None, edit_observacao)
                                        if success:
                                            st.success(message)
                                            st.rerun()
                                        else:
                                            st.error(message)
                                    else:
                                        st.error("❌ Por favor, preencha o setor e a data de entrada para atualizar.")

                                if submitted_delete_tram:
                                    if st.warning(f"Tem certeza que deseja deletar a tramitação ID {dados_tram[0]}?"):
                                        if st.button("CONFIRMAR DELETAR TRAMITAÇÃO", key="confirm_delete_tram", type="danger"):
                                            success, message = deletar_tramitacao(tramitacao_selecionada_id)
                                            if success:
                                                st.success(message)
                                                st.rerun()
                                            else:
                                                st.error(message)
                else:
                    st.info("Nenhuma tramitação para editar ou deletar.")

    with tab4:
        st.header("🔍 Análise de Projeto com IA")
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

    with tab5: # A aba de gráficos agora é a tab5
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

    with tab6: # A aba de configurações DB agora é a tab6
        st.header("⚙️ Configurações do Banco de Dados")
        st.warning("⚠️ Cuidado: As ações nesta aba são irreversíveis e podem apagar todos os seus dados.")
        if st.button("🔴 Resetar Banco de Dados (Apagar TUDO!)", type="danger", key="reset_db_button_final"):
            # A função reset_database foi removida, então a lógica de reset é direta aqui.
            try:
                if os.path.exists('processos.db'):
                    os.remove('processos.db')
                st.cache_resource.clear()
                st.session_state['db_reset_needed_rerun'] = True
                st.success("✅ Banco de dados resetado com sucesso! A página será recarregada.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erro ao resetar o banco de dados: {str(e)}")


# ==================== LÓGICA PRINCIPAL DO APP ====================
# O aplicativo agora inicia diretamente no conteúdo principal, sem tela de login.
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

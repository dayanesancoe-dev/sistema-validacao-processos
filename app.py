import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime, date
import sqlite3
import os
import io # Importar io para lidar com arquivos em memória

# ==================== CONFIGURAÇÃO INICIAL ====================
st.set_page_config(page_title="Sistema de Validação", page_icon="🏛️", layout="wide")

# Tentativa segura de importar bibliotecas gráficas
try:
    import pandas as pd
    import plotly.express as px
except ImportError:
    pd = None
    px = None
    st.error("❌ Erro: As bibliotecas 'pandas' e 'plotly' não foram encontradas. A aba de gráficos não funcionará. Por favor, verifique seu 'requirements.txt' e faça um 'Clear cache and redeploy' no Streamlit Share.")

# ==================== BANCO DE DADOS ====================
@st.cache_resource
def init_db():
    try:
        conn = sqlite3.connect('processos.db', check_same_thread=False)
        c = conn.cursor()
        # Tabelas
        c.execute('''CREATE TABLE IF NOT EXISTS processos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT UNIQUE NOT NULL,
            rt TEXT, requerente TEXT, analista TEXT, uso TEXT, 
            tipologia TEXT, area REAL, data_protocolo TEXT,
            status TEXT DEFAULT 'Protocolado',
            data_cadastro TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS tramitacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_id INTEGER, setor TEXT, data_entrada TEXT, 
            data_saida TEXT, observacao TEXT,
            FOREIGN KEY (processo_id) REFERENCES processos(id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS analises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_id INTEGER, resultado TEXT, status TEXT, 
            data_analise TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (processo_id) REFERENCES processos(id)
        )''')
        # === CORREÇÃO DE NOMES DE SETORES ANTIGOS ===
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
        st.error(f"Erro no Banco de Dados: {e}")
        return None

conn = init_db()

# ==================== FUNÇÕES AUXILIARES ====================
def executar_query(query, params=(), commit=False):
    if not conn: 
        st.error("❌ Erro: Conexão com o banco de dados não estabelecida.")
        return False, "Sem conexão com o banco de dados."
    try:
        c = conn.cursor()
        c.execute(query, params)
        if commit: conn.commit()
        return True, c
    except sqlite3.IntegrityError as e:
        return False, f"Erro de integridade no banco de dados: {str(e)}. Verifique se o número do processo já existe ou se há chaves duplicadas."
    except Exception as e:
        return False, f"Erro ao executar query: {str(e)}"

def listar_processos():
    suc, res = executar_query('SELECT * FROM processos ORDER BY id DESC')
    return res.fetchall() if suc else []

def buscar_processo(numero_ou_id):
    query = 'SELECT * FROM processos WHERE id = ?' if isinstance(numero_ou_id, int) else 'SELECT * FROM processos WHERE numero = ?'
    suc, res = executar_query(query, (numero_ou_id,))
    return res.fetchone() if suc else None

def get_processos_df():
    if not conn: return pd.DataFrame()
    try:
        df = pd.read_sql_query("SELECT * FROM processos", conn)
        df['data_protocolo'] = pd.to_datetime(df['data_protocolo'], errors='coerce')
        return df
    except Exception:
        return pd.DataFrame()

def cadastrar_processo(numero, rt, requerente, analista, uso, tipologia, area, data_protocolo):
    suc, res = executar_query(
        "INSERT INTO processos (numero, rt, requerente, analista, uso, tipologia, area, data_protocolo) VALUES (?,?,?,?,?,?,?,?)",
        (numero, rt, requerente, analista, uso, tipologia, area, data_protocolo),
        commit=True
    )
    return suc, res

def atualizar_processo(pid, numero, rt, requerente, analista, uso, tipologia, area, data_protocolo, status):
    suc, res = executar_query(
        "UPDATE processos SET numero=?, rt=?, requerente=?, analista=?, uso=?, tipologia=?, area=?, data_protocolo=?, status=? WHERE id=?",
        (numero, rt, requerente, analista, uso, tipologia, area, data_protocolo, status, pid),
        commit=True
    )
    return suc, res

def deletar_processo(pid):
    try:
        # Deletar análises e tramitações relacionadas primeiro
        executar_query("DELETE FROM analises WHERE processo_id=?", (pid,), commit=True)
        executar_query("DELETE FROM tramitacao WHERE processo_id=?", (pid,), commit=True)
        suc, res = executar_query("DELETE FROM processos WHERE id=?", (pid,), commit=True)
        return suc, res
    except Exception as e:
        return False, f"❌ Erro ao deletar processo: {str(e)}"

def registrar_tramitacao(processo_id, setor, data_entrada, data_saida, observacao):
    # Primeiro, fechar qualquer tramitação anterior em aberto para este processo_id no mesmo setor
    # ou simplesmente garantir que a data de saída da tramitação anterior seja preenchida
    # Vamos simplificar: se houver uma tramitação anterior *sem data de saída* para este processo,
    # atualizamos a data de saída dela para a data de entrada da nova tramitação.

    # Busca a última tramitação em aberto para este processo
    suc_last, last_tram = executar_query(
        "SELECT id, data_entrada FROM tramitacao WHERE processo_id = ? AND data_saida IS NULL ORDER BY data_entrada DESC LIMIT 1",
        (processo_id,)
    )

    if suc_last and last_tram.fetchone(): # Se encontrou uma tramitação anterior em aberto
        last_tram_id, last_tram_data_entrada = last_tram.fetchone() # Re-fetch, cursor moves
        # Atualiza a data de saída da tramitação anterior para a data de entrada da nova
        suc_upd, msg_upd = executar_query(
            "UPDATE tramitacao SET data_saida = ? WHERE id = ?",
            (data_entrada, last_tram_id),
            commit=True
        )
        if not suc_upd:
            return False, f"Erro ao fechar tramitação anterior: {msg_upd}"

    # Insere a nova tramitação
    suc_ins, res_ins = executar_query(
        "INSERT INTO tramitacao (processo_id, setor, data_entrada, data_saida, observacao) VALUES (?,?,?,?,?)",
        (processo_id, setor, data_entrada, data_saida, observacao),
        commit=True
    )
    return suc_ins, res_ins

def listar_tramitacoes(processo_id):
    suc, res = executar_query('SELECT * FROM tramitacao WHERE processo_id = ? ORDER BY data_entrada DESC', (processo_id,))
    return res.fetchall() if suc else []

def atualizar_tramitacao(tid, setor, data_entrada, data_saida, observacao):
    suc, res = executar_query(
        "UPDATE tramitacao SET setor=?, data_entrada=?, data_saida=?, observacao=? WHERE id=?",
        (setor, data_entrada, data_saida, observacao, tid),
        commit=True
    )
    return suc, res

def deletar_tramitacao(tid):
    suc, res = executar_query("DELETE FROM tramitacao WHERE id=?", (tid,), commit=True)
    return suc, res

def registrar_analise(processo_id, resultado, status):
    suc, res = executar_query(
        "INSERT INTO analises (processo_id, resultado, status) VALUES (?,?,?)",
        (processo_id, resultado, status),
        commit=True
    )
    return suc, res

def listar_analises(processo_id):
    suc, res = executar_query('SELECT * FROM analises WHERE processo_id = ? ORDER BY data_analise DESC', (processo_id,))
    return res.fetchall() if suc else []

# ==================== FUNÇÕES DE IA ====================
def configurar_gemini(api_key):
    try:
        genai.configure(api_key=api_key)
        st.session_state['gemini_configured'] = True
        st.success("API Key configurada com sucesso!")
    except Exception as e:
        st.session_state['gemini_configured'] = False
        st.error(f"Erro ao configurar a API Key: {e}")

def extrair_texto_pdf(uploaded_file):
    if uploaded_file is not None:
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() or ""
        return text
    return None

def analisar_documento_gemini(document_text, prompt_base):
    if not st.session_state.get('gemini_configured'):
        st.error("API Key do Gemini não configurada. Por favor, configure-a na barra lateral.")
        return "Erro: API Key não configurada."

    try:
        model = genai.GenerativeModel('gemini-pro')
        full_prompt = f"{prompt_base}\n\nConteúdo do Documento:\n{document_text}"
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"Erro ao chamar a API do Gemini: {e}"

# ==================== LAYOUT E LÓGICA DO APP ====================

# === LOGIN ===
def login_form():
    st.sidebar.image("https://www.contagem.mg.gov.br/portal/uploads/2023/07/logo-contagem-2023.png", width=200)
    st.sidebar.title("Login no Sistema")

    with st.sidebar.form("login_form"):
        st.markdown("### Acesso Restrito")
        user = st.text_input("Usuário", key="login_user")
        pwd = st.text_input("Senha", type="password", key="login_pwd")
        submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)

        if submitted:
            admin_username = st.secrets.get("admin_user", {}).get("username")
            admin_password = st.secrets.get("admin_user", {}).get("password")

            if admin_username is None or admin_password is None:
                st.error("❌ Credenciais de administrador não configuradas corretamente no '.streamlit/secrets.toml'.")
                st.info("Por favor, verifique se a seção '[admin_user]' com 'username' e 'password' está presente e correta.")
                return

            if user == admin_username and pwd == admin_password:
                st.session_state['logged_in'] = True
                st.success("Login realizado com sucesso!")
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")

# === CONTEÚDO PRINCIPAL DO APP ===
def main_app_content():
    st.sidebar.image("https://www.contagem.mg.gov.br/portal/uploads/2023/07/logo-contagem-2023.png", width=200)
    st.sidebar.title("🏛️ Sistema de Validação")
    st.sidebar.write(f"Bem-vindo(a), admin!")

    # --- Opções da Barra Lateral ---
    st.sidebar.subheader("Configurações")
    with st.sidebar.expander("API Key Gemini"):
        api_key_input = st.text_input("Insira sua API Key do Google Gemini", type="password", value=st.session_state['api_key'])
        if st.button("Configurar API Key", key="config_api_key_btn"):
            if api_key_input:
                st.session_state['api_key'] = api_key_input
                configurar_gemini(api_key_input)
            else:
                st.warning("Por favor, insira uma API Key.")

    st.sidebar.subheader("Ferramentas de Banco de Dados")
    # --- Opção de Backup ---
    if st.sidebar.button("💾 Fazer Backup do Banco de Dados", key="backup_db_btn"):
        try:
            with open('processos.db', 'rb') as f:
                st.sidebar.download_button(
                    label="Download Backup",
                    data=f.read(),
                    file_name="processos_backup.db",
                    mime="application/octet-stream",
                    key="download_backup_btn"
                )
            st.sidebar.success("Backup pronto para download!")
        except Exception as e:
            st.sidebar.error(f"Erro ao fazer backup: {e}")

    # --- Opção de Carregar Backup (RESTAURADA AQUI) ---
    uploaded_backup = st.sidebar.file_uploader("⬆️ Carregar Backup do Banco de Dados", type=['db'], key="upload_backup_uploader")
    if uploaded_backup is not None:
        if st.sidebar.button("Restaurar Backup", key="restore_backup_btn"):
            try:
                # Fechar a conexão atual antes de substituir o arquivo
                if conn:
                    conn.close()

                # Salvar o arquivo carregado como 'processos.db'
                with open('processos.db', 'wb') as f:
                    f.write(uploaded_backup.getvalue())

                # Re-inicializar a conexão com o novo banco de dados
                st.cache_resource.clear() # Limpa o cache para init_db ser chamado novamente
                global conn # Declara conn como global para poder reatribuir
                conn = init_db()

                if conn:
                    st.sidebar.success("Backup restaurado com sucesso! O aplicativo será reiniciado.")
                    st.rerun() # Reinicia o app para carregar os novos dados
                else:
                    st.sidebar.error("Erro ao re-inicializar o banco de dados após a restauração.")
            except Exception as e:
                st.sidebar.error(f"Erro ao restaurar backup: {e}")

    if st.sidebar.button("Sair", type="secondary", use_container_width=True, key="logout_btn"):
        st.session_state['logged_in'] = False
        st.session_state['gemini_configured'] = False
        st.session_state['api_key'] = ''
        st.rerun()

    st.title("🏛️ Sistema de Validação de Processos")
    st.markdown("Gerencie seus processos, tramitações e análises com o poder da IA.")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["➕ Cadastrar Processo", "📝 Listar e Gerenciar", "➡️ Tramitação", "🤖 Análise IA", "📊 Gráficos e Métricas"])

    # ==================== ABA 1: CADASTRAR PROCESSO ====================
    with tab1:
        st.header("➕ Cadastrar Novo Processo")
        with st.form("cadastro_processo_form"):
            col1, col2 = st.columns(2)
            with col1:
                numero = st.text_input("Número do Processo", help="Número único de identificação do processo.", key="cad_numero").strip()
                rt = st.text_input("RT (Responsável Técnico)", key="cad_rt").strip()
                requerente = st.text_input("Requerente", key="cad_requerente").strip()
                analista = st.text_input("Analista Responsável", key="cad_analista").strip()
            with col2:
                usos_comuns = ["Residencial", "Comercial", "Industrial", "Misto", "Institucional", "Outro"]
                uso = st.selectbox("Uso Predominante", options=usos_comuns, key="cad_uso")
                if uso == "Outro":
                    uso = st.text_input("Especifique o Uso", key="cad_uso_outro").strip()

                tipologias_comuns = ["Unifamiliar", "Multifamiliar", "Comercial", "Serviços", "Galpão", "Misto", "Outro"]
                tipologia = st.selectbox("Tipologia do Projeto", options=tipologias_comuns, key="cad_tipologia")
                if tipologia == "Outro":
                    tipologia = st.text_input("Especifique a Tipologia", key="cad_tipologia_outro").strip()

                area = st.number_input("Área (m²)", min_value=0.0, format="%.2f", key="cad_area")
                data_protocolo = st.date_input("Data de Protocolo", value="today", key="cad_data_protocolo")

            submitted = st.form_submit_button("Cadastrar Processo", type="primary", use_container_width=True)

            if submitted:
                if numero and requerente and uso and tipologia and area >= 0:
                    suc, msg = cadastrar_processo(numero, rt, requerente, analista, uso, tipologia, area, data_protocolo.strftime('%Y-%m-%d'))
                    if suc:
                        st.success(f"Processo {numero} cadastrado com sucesso!")
                        st.rerun()
                    else:
                        st.error(f"Erro ao cadastrar processo: {msg}")
                else:
                    st.warning("Por favor, preencha todos os campos obrigatórios (Número, Requerente, Uso, Tipologia, Área).")

    # ==================== ABA 2: LISTAR E GERENCIAR PROCESSOS ====================
    with tab2:
        st.header("📝 Listar e Gerenciar Processos")
        processos = listar_processos()
        if not processos:
            st.info("📭 Nenhum processo cadastrado ainda.")
        else:
            df_processos = pd.DataFrame(processos, columns=["ID", "Número", "RT", "Requerente", "Analista", "Uso", "Tipologia", "Área", "Status", "Data Cadastro"])

            # Filtro de busca
            search_term = st.text_input("Buscar por Número, Requerente ou Analista:", key="search_processos").strip()
            if search_term:
                df_processos_filtered = df_processos[
                    df_processos['Número'].str.contains(search_term, case=False, na=False) |
                    df_processos['Requerente'].str.contains(search_term, case=False, na=False) |
                    df_processos['Analista'].str.contains(search_term, case=False, na=False)
                ]
            else:
                df_processos_filtered = df_processos

            st.dataframe(df_processos_filtered, use_container_width=True)

            st.subheader("Atualizar ou Deletar Processo")

            # Usar um selectbox para selecionar o processo
            processo_options = [(p[0], p[1]) for p in processos] # (ID, Número)
            processo_selecionado_tuple = st.selectbox(
                "Selecione o Processo pelo ID ou Número:",
                options=processo_options,
                format_func=lambda x: f"ID: {x[0]} - Número: {x[1]}",
                key="select_processo_edit_del"
            )

            if processo_selecionado_tuple:
                pid_selecionado = processo_selecionado_tuple[0]
                dados_processo = buscar_processo(pid_selecionado) # Buscar por ID

                if dados_processo:
                    st.write(f"DEBUG: pid_selecionado = {pid_selecionado}") # Linha de DEBUG
                    with st.form(f"edit_processo_form_{pid_selecionado}"):
                        col_upd1, col_upd2 = st.columns(2)
                        with col_upd1:
                            upd_numero = st.text_input("Número do Processo", value=dados_processo[1], key=f"upd_numero_{pid_selecionado}").strip()
                            upd_rt = st.text_input("RT", value=dados_processo[2], key=f"upd_rt_{pid_selecionado}").strip()
                            upd_requerente = st.text_input("Requerente", value=dados_processo[3], key=f"upd_requerente_{pid_selecionado}").strip()
                            upd_analista = st.text_input("Analista", value=dados_processo[4], key=f"upd_analista_{pid_selecionado}").strip()
                        with col_upd2:
                            upd_uso = st.selectbox("Uso", options=["Residencial", "Comercial", "Industrial", "Misto", "Institucional", "Outro"], index=["Residencial", "Comercial", "Industrial", "Misto", "Institucional", "Outro"].index(dados_processo[5]) if dados_processo[5] in ["Residencial", "Comercial", "Industrial", "Misto", "Institucional", "Outro"] else 0, key=f"upd_uso_{pid_selecionado}")
                            upd_tipologia = st.selectbox("Tipologia", options=["Unifamiliar", "Multifamiliar", "Comercial", "Serviços", "Galpão", "Misto", "Outro"], index=["Unifamiliar", "Multifamiliar", "Comercial", "Serviços", "Galpão", "Misto", "Outro"].index(dados_processo[6]) if dados_processo[6] in ["Unifamiliar", "Multifamiliar", "Comercial", "Serviços", "Galpão", "Misto", "Outro"] else 0, key=f"upd_tipologia_{pid_selecionado}")
                            upd_area = st.number_input("Área (m²)", value=float(dados_processo[7]), min_value=0.0, format="%.2f", key=f"upd_area_{pid_selecionado}")
                            upd_data_protocolo = st.date_input("Data de Protocolo", value=datetime.strptime(dados_processo[8], '%Y-%m-%d').date(), key=f"upd_data_protocolo_{pid_selecionado}")
                            upd_status = st.selectbox("Status", options=["Protocolado", "Em Análise", "Aprovado", "Reprovado", "Arquivado"], index=["Protocolado", "Em Análise", "Aprovado", "Reprovado", "Arquivado"].index(dados_processo[9]), key=f"upd_status_{pid_selecionado}")

                        col_btns_upd, col_btns_del = st.columns(2)
                        with col_btns_upd:
                            submitted_update = st.form_submit_button("Atualizar Processo", type="primary", use_container_width=True, key=f"submit_update_{pid_selecionado}")
                        with col_btns_del:
                            submitted_delete = st.form_submit_button("Deletar Processo", type="danger", use_container_width=True, key=f"submit_delete_{pid_selecionado}")

                        if submitted_update:
                            if upd_numero and upd_requerente and upd_uso and upd_tipologia and upd_area >= 0:
                                suc, msg = atualizar_processo(pid_selecionado, upd_numero, upd_rt, upd_requerente, upd_analista, upd_uso, upd_tipologia, upd_area, upd_data_protocolo.strftime('%Y-%m-%d'), upd_status)
                                if suc:
                                    st.success(f"Processo {upd_numero} atualizado com sucesso!")
                                    st.rerun()
                                else:
                                    st.error(f"Erro ao atualizar processo: {msg}")
                            else:
                                st.warning("Por favor, preencha todos os campos obrigatórios para atualização.")

                        if submitted_delete:
                            st.warning(f"Tem certeza que deseja deletar o processo {dados_processo[1]}? Todas as tramitações e análises associadas também serão deletadas.")
                            confirm_deletion = st.checkbox("Sim, eu confirmo a deleção deste processo e seus dados relacionados.", key=f"confirm_checkbox_delete_{pid_selecionado}")
                            if confirm_deletion:
                                suc, msg = deletar_processo(pid_selecionado)
                                if suc:
                                    st.success(f"Processo {dados_processo[1]} deletado com sucesso!")
                                    st.rerun()
                                else:
                                    st.error(f"Erro ao deletar processo: {msg}")
                else:
                    st.info("Selecione um processo para ver os detalhes.")

    # ==================== ABA 3: TRAMITAÇÃO ====================
    with tab3:
        st.header("➡️ Tramitação de Processos")
        processos_tram = listar_processos()
        if not processos_tram:
            st.info("📭 Nenhum processo cadastrado para tramitação.")
        else:
            processo_options_tram = [(p[0], p[1]) for p in processos_tram] # (ID, Número)
            processo_selecionado_tramitacao_tuple = st.selectbox(
                "Selecione o Processo para Tramitação:",
                options=processo_options_tram,
                format_func=lambda x: f"ID: {x[0]} - Número: {x[1]}",
                key="select_processo_tramitacao"
            )

            if processo_selecionado_tramitacao_tuple:
                pid_tramitacao = processo_selecionado_tramitacao_tuple[0]
                dados_processo_tram = buscar_processo(pid_tramitacao)

                if dados_processo_tram:
                    st.markdown(f"### Processo Selecionado: **{dados_processo_tram[1]}** - Requerente: **{dados_processo_tram[3]}**")
                    st.markdown(f"Status Atual: **{dados_processo_tram[9]}**")
                    st.divider()

                    st.markdown("#### Registrar Nova Movimentação")
                    with st.form(f"form_nova_tramitacao_{pid_tramitacao}"):
                        col_tram1, col_tram2 = st.columns(2)
                        with col_tram1:
                            setores = ["Protocolo", "Pré-análise", "Análise Técnica", "Coordenação", "Secretaria", "Arquivo", "Outro"]
                            novo_setor = st.selectbox("Setor Destino", options=setores, key=f"novo_setor_{pid_tramitacao}")
                            if novo_setor == "Outro":
                                novo_setor = st.text_input("Especifique o Setor", key=f"novo_setor_outro_{pid_tramitacao}").strip()

                            data_entrada_nova = st.date_input("Data de Entrada", value="today", key=f"data_entrada_nova_{pid_tramitacao}")

                        with col_tram2:
                            observacao_nova = st.text_area("Observação", key=f"observacao_nova_{pid_tramitacao}").strip()

                            tem_saida_nova = st.checkbox("Informar Data de Saída?", key=f"tem_saida_nova_{pid_tramitacao}")
                            data_saida_nova = None
                            if tem_saida_nova:
                                data_saida_nova = st.date_input("Data de Saída", value="today", key=f"data_saida_nova_{pid_tramitacao}")
                                if data_saida_nova < data_entrada_nova:
                                    st.error("A Data de Saída não pode ser anterior à Data de Entrada.")
                                    data_saida_nova = None # Invalidar a data de saída

                        submitted_tram = st.form_submit_button("Registrar Tramitação", type="primary", use_container_width=True, key=f"submit_tram_{pid_tramitacao}")

                        if submitted_tram:
                            if novo_setor and data_entrada_nova:
                                # Formatar datas para string YYYY-MM-DD
                                data_entrada_str = data_entrada_nova.strftime('%Y-%m-%d')
                                data_saida_str = data_saida_nova.strftime('%Y-%m-%d') if data_saida_nova else None

                                suc, msg = registrar_tramitacao(pid_tramitacao, novo_setor, data_entrada_str, data_saida_str, observacao_nova)
                                if suc:
                                    st.success("Movimentação registrada com sucesso!")
                                    st.rerun()
                                else:
                                    st.error(f"Erro ao registrar movimentação: {msg}")
                            else:
                                st.warning("Por favor, preencha o Setor Destino e a Data de Entrada.")

                    st.divider()
                    st.markdown("#### Histórico de Tramitações")
                    tramitacoes = listar_tramitacoes(pid_tramitacao)
                    if tramitacoes:
                        df_tramitacoes = pd.DataFrame(tramitacoes, columns=["ID", "Processo ID", "Setor", "Data Entrada", "Data Saída", "Observação"])
                        st.dataframe(df_tramitacoes, use_container_width=True)
                    else:
                        st.info("Nenhuma movimentação registrada para este processo.")

                    st.divider()
                    st.markdown("#### Editar ou Deletar Movimentação")
                    if tramitacoes:
                        tramitacao_options = [(t[0], t[2], t[3]) for t in tramitacoes] # (ID, Setor, Data Entrada)
                        tramitacao_selecionada_tuple = st.selectbox(
                            "Selecione a Movimentação para Editar/Deletar:",
                            options=tramitacao_options,
                            format_func=lambda x: f"ID: {x[0]} - Setor: {x[1]} - Entrada: {x[2]}",
                            key=f"select_tramitacao_edit_del_{pid_tramitacao}"
                        )

                        if tramitacao_selecionada_tuple:
                            tid_selecionado = tramitacao_selecionada_tuple[0]
                            dados_tramitacao = next((t for t in tramitacoes if t[0] == tid_selecionado), None)

                            if dados_tramitacao:
                                with st.form(f"form_edit_tramitacao_{tid_selecionado}"):
                                    col_edit_tram1, col_edit_tram2 = st.columns(2)
                                    with col_edit_tram1:
                                        edit_setor = st.selectbox("Setor", options=setores, index=setores.index(dados_tramitacao[2]) if dados_tramitacao[2] in setores else 0, key=f"edit_setor_{tid_selecionado}")
                                        if edit_setor == "Outro":
                                            edit_setor = st.text_input("Especifique o Setor", value=dados_tramitacao[2], key=f"edit_setor_outro_{tid_selecionado}").strip()

                                        edit_data_entrada = st.date_input("Data de Entrada", value=datetime.strptime(dados_tramitacao[3], '%Y-%m-%d').date(), key=f"edit_data_entrada_{tid_selecionado}")

                                    with col_edit_tram2:
                                        edit_observacao = st.text_area("Observação", value=dados_tramitacao[5], key=f"edit_observacao_{tid_selecionado}").strip()

                                        has_saida = dados_tramitacao[4] is not None
                                        edit_tem_saida = st.checkbox("Informar Data de Saída?", value=has_saida, key=f"edit_tem_saida_{tid_selecionado}")
                                        edit_data_saida = None
                                        if edit_tem_saida:
                                            edit_data_saida = st.date_input("Data de Saída", value=datetime.strptime(dados_tramitacao[4], '%Y-%m-%d').date() if has_saida else "today", key=f"edit_data_saida_{tid_selecionado}")
                                            if edit_data_saida < edit_data_entrada:
                                                st.error("A Data de Saída não pode ser anterior à Data de Entrada.")
                                                edit_data_saida = None # Invalidar a data de saída

                                    col_upd_tram, col_del_tram = st.columns(2)
                                    with col_upd_tram:
                                        submitted_update_tram = st.form_submit_button("Atualizar Movimentação", type="primary", use_container_width=True, key=f"submit_update_tram_{tid_selecionado}")
                                    with col_del_tram:
                                        submitted_delete_tram = st.form_submit_button("Deletar Movimentação", type="danger", use_container_width=True, key=f"submit_delete_tram_{tid_selecionado}")

                                    if submitted_update_tram:
                                        if edit_setor and edit_data_entrada:
                                            edit_data_entrada_str = edit_data_entrada.strftime('%Y-%m-%d')
                                            edit_data_saida_str = edit_data_saida.strftime('%Y-%m-%d') if edit_data_saida else None

                                            suc, msg = atualizar_tramitacao(tid_selecionado, edit_setor, edit_data_entrada_str, edit_data_saida_str, edit_observacao)
                                            if suc:
                                                st.success("Movimentação atualizada com sucesso!")
                                                st.rerun()
                                            else:
                                                st.error(f"Erro ao atualizar movimentação: {msg}")
                                        else:
                                            st.warning("Por favor, preencha o Setor e a Data de Entrada para atualização.")

                                    if submitted_delete_tram:
                                        st.warning(f"Tem certeza que deseja deletar a movimentação ID {dados_tramitacao[0]}?")
                                        confirm_tram_deletion = st.checkbox("Sim, eu confirmo a deleção desta movimentação.", key=f"confirm_checkbox_delete_tram_{tid_selecionado}")
                                        if confirm_tram_deletion:
                                            suc, msg = deletar_tramitacao(tid_selecionado)
                                            if suc:
                                                st.success(f"Movimentação ID {dados_tramitacao[0]} deletada com sucesso!")
                                                st.rerun()
                                            else:
                                                st.error(f"Erro ao deletar movimentação: {msg}")
                    else:
                        st.info("Nenhuma movimentação para editar ou deletar.")

    # ==================== ABA 4: ANÁLISE IA ====================
    with tab4:
        st.header("🤖 Análise de Documentos com IA (Google Gemini)")
        if not st.session_state.get('gemini_configured'):
            st.warning("Por favor, configure sua API Key do Google Gemini na barra lateral para usar esta funcionalidade.")
        else:
            processos_analise = listar_processos()
            if not processos_analise:
                st.info("📭 Nenhum processo cadastrado para análise.")
            else:
                processo_options_analise = [(p[0], p[1]) for p in processos_analise] # (ID, Número)
                processo_selecionado_analise_tuple = st.selectbox(
                    "Selecione o Processo para Análise:",
                    options=processo_options_analise,
                    format_func=lambda x: f"ID: {x[0]} - Número: {x[1]}",
                    key="select_processo_analise"
                )

                if processo_selecionado_analise_tuple:
                    pid_analise = processo_selecionado_analise_tuple[0]
                    dados_processo_analise = buscar_processo(pid_analise)

                    if dados_processo_analise:
                        st.markdown(f"### Processo Selecionado: **{dados_processo_analise[1]}** - Requerente: **{dados_processo_analise[3]}**")
                        st.divider()

                        uploaded_file = st.file_uploader("Carregar Documento PDF para Análise", type=["pdf"], key=f"pdf_uploader_{pid_analise}")

                        if uploaded_file:
                            st.success("PDF carregado com sucesso! Clique em 'Analisar Documento' para iniciar.")

                            prompt_options = {
                                "Análise de Conformidade": "Analise o documento para verificar a conformidade com as normas de construção. Identifique pontos de atenção, não conformidades e sugestões de melhoria. Retorne a análise de forma estruturada, com um resumo e uma lista de itens.",
                                "Extração de Dados Chave": "Extraia do documento os seguintes dados: Número do Processo, Requerente, RT, Área Total, Uso, Tipologia, Data de Protocolo. Se não encontrar algum dado, indique 'Não encontrado'.",
                                "Resumo do Documento": "Faça um resumo conciso do documento, destacando os pontos mais importantes e as principais informações.",
                                "Outro (Personalizado)": "Permite que você digite um prompt personalizado."
                            }

                            selected_prompt_type = st.selectbox("Escolha o tipo de análise:", list(prompt_options.keys()), key=f"prompt_type_{pid_analise}")

                            custom_prompt = ""
                            if selected_prompt_type == "Outro (Personalizado)":
                                custom_prompt = st.text_area("Digite seu prompt personalizado para o Gemini:", height=150, key=f"custom_prompt_{pid_analise}")
                                prompt_base = custom_prompt
                            else:
                                prompt_base = prompt_options[selected_prompt_type]

                            if st.button("Analisar Documento com IA", type="primary", use_container_width=True, key=f"analisar_btn_{pid_analise}"):
                                with st.spinner("Analisando documento com IA... Isso pode levar alguns segundos."):
                                    document_text = extrair_texto_pdf(uploaded_file)
                                    if document_text:
                                        if prompt_base:
                                            ia_result = analisar_documento_gemini(document_text, prompt_base)
                                            st.subheader("Resultado da Análise da IA:")
                                            st.write(ia_result)

                                            st.divider()
                                            st.markdown("#### Registrar Resultado da Análise")
                                            with st.form(f"form_registrar_analise_{pid_analise}"):
                                                analise_status = st.selectbox("Status da Análise", options=["Conforme", "Não Conforme", "Parcialmente Conforme", "Em Revisão"], key=f"analise_status_{pid_analise}")
                                                submitted_analise = st.form_submit_button("Salvar Análise", type="secondary", key=f"submit_analise_{pid_analise}")
                                                if submitted_analise:
                                                    suc, msg = registrar_analise(pid_analise, ia_result, analise_status)
                                                    if suc:
                                                        st.success("Análise registrada com sucesso!")
                                                        st.rerun()
                                                    else:
                                                        st.error(f"Erro ao registrar análise: {msg}")
                                        else:
                                            st.warning("Por favor, selecione ou digite um prompt para a análise.")
                                    else:
                                        st.error("Não foi possível extrair texto do PDF.")

                        st.divider()
                        st.markdown("#### Histórico de Análises de IA")
                        analises = listar_analises(pid_analise)
                        if analises:
                            df_analises = pd.DataFrame(analises, columns=["ID", "Processo ID", "Resultado", "Status", "Data Análise"])
                            st.dataframe(df_analises, use_container_width=True)
                        else:
                            st.info("Nenhuma análise de IA registrada para este processo.")
                else:
                    st.info("Selecione um processo para iniciar a análise de IA.")

    # ==================== ABA 5: GRÁFICOS E MÉTRICAS ====================
    with tab5:
        st.header("📊 Gráficos e Métricas do Sistema")
        if pd is None or px is None:
            st.error("As bibliotecas 'pandas' e 'plotly' não estão disponíveis. Não é possível exibir gráficos.")
            st.stop() # Parar a execução desta aba se as libs não estiverem presentes

        procs_df = get_processos_df()
        if procs_df.empty:
            st.info("Nenhum dado de processo disponível para gerar gráficos.")
        else:
            st.subheader("Métricas Chave")
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_m1.metric("Total de Processos", len(procs_df))
            col_m2.metric("Área Total Cadastrada", f"{procs_df['Área'].sum():,.2f} m²")

            processos_em_analise = procs_df[procs_df['Status'] == 'Em Análise']
            col_m3.metric("Processos Em Análise", len(processos_em_analise))

            # Média de dias em tramitação (para processos com data de saída)
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
                df_grouped = procs_df['Status'].value_counts().reset_index()
                df_grouped.columns = ['Status', 'Quantidade']
                fig = px.pie(df_grouped, values='Quantidade', names='Status', 
                             title='Distribuição Percentual de Processos por Status',
                             hole=0.3, 
                             template='plotly_white')
                st.plotly_chart(fig, use_container_width=True)

            elif chart_type == "Processos por Uso":
                st.markdown("### 📊 Quantidade de Processos por Tipo de Uso")
                df_grouped = procs_df['Uso'].value_counts().reset_index()
                df_grouped.columns = ['Uso', 'Quantidade']
                fig = px.bar(df_grouped, x='Uso', y='Quantidade', 
                             title='Número de Processos por Tipo de Uso',
                             labels={'Uso': 'Tipo de Uso', 'Quantidade': 'Número de Processos'},
                             color='Uso', 
                             template='plotly_white')
                st.plotly_chart(fig, use_container_width=True)

            elif chart_type == "Processos por Tipologia":
                st.markdown("### 📊 Quantidade de Processos por Tipologia")
                df_grouped = procs_df['Tipologia'].value_counts().reset_index()
                df_grouped.columns = ['Tipologia', 'Quantidade']
                fig = px.bar(df_grouped, x='Tipologia', y='Quantidade', 
                             title='Número de Processos por Tipologia',
                             labels={'Tipologia': 'Tipologia do Projeto', 'Quantidade': 'Número de Processos'},
                             color='Tipologia',
                             template='plotly_white')
                st.plotly_chart(fig, use_container_width=True)

            elif chart_type == "Processos por Analista":
                st.markdown("### 📊 Quantidade de Processos por Analista")
                df_grouped = procs_df['Analista'].value_counts().reset_index()
                df_grouped.columns = ['Analista', 'Quantidade']
                fig = px.bar(df_grouped, x='Analista', y='Quantidade', 
                             title='Número de Processos por Analista',
                             labels={'Analista': 'Nome do Analista', 'Quantidade': 'Número de Processos'},
                             color='Analista',
                             template='plotly_white')
                st.plotly_chart(fig, use_container_width=True)

            elif chart_type == "Área Total por Uso":
                st.markdown("### 📊 Área Construída Total por Tipo de Uso")
                df_grouped = procs_df.groupby('Uso')['Área'].sum().reset_index()
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

# ==================== LÓGICA PRINCIPAL DO APP ====================
if not st.session_state.get('logged_in', False): # Garante que 'logged_in' é False se não existir
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

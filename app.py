import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime, timedelta
import sqlite3
import os
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Sistema de Validação", page_icon="🏛️", layout="wide")

# ==================== INICIALIZAÇÃO DE ESTADO ====================
# Garante que a API Key esteja sempre inicializada
if 'api_key' not in st.session_state:
    st.session_state['api_key'] = ''

# Flag para forçar rerun após reset do banco
if 'db_reset_needed_rerun' not in st.session_state:
    st.session_state['db_reset_needed_rerun'] = False

if st.session_state['db_reset_needed_rerun']:
    st.session_state['db_reset_needed_rerun'] = False
    st.experimental_rerun()

# ==================== BANCO DE DADOS ====================

def reset_database():
    """Reseta o banco de dados, removendo o arquivo e limpando o cache."""
    try:
        if os.path.exists('processos.db'):
            os.remove('processos.db')
        st.cache_resource.clear() # Limpa o cache para forçar a recriação da conexão
        st.session_state['db_reset_needed_rerun'] = True # Define a flag para forçar rerun
        st.success("✅ Banco de dados resetado com sucesso! A página será recarregada.")
        st.experimental_rerun() # Força o rerun
    except Exception as e:
        st.error(f"❌ Erro ao resetar o banco de dados: {str(e)}")
        return None

@st.cache_resource
def init_db():
    """Inicializa o banco de dados, criando tabelas se não existirem ou se o schema estiver desatualizado."""
    try:
        conn = sqlite3.connect('processos.db', check_same_thread=False)
        c = conn.cursor()

        # Verificar se a tabela 'processos' existe
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processos'")
        table_exists = c.fetchone()

        # Definir o schema esperado para a tabela 'processos'
        expected_processos_column_names = [
            'id', 'numero', 'rt', 'requerente', 'analista', 'uso', 
            'tipologia', 'area', 'data_protocolo', 'status', 'data_cadastro'
        ]

        schema_outdated = False

        if table_exists:
            c.execute("PRAGMA table_info(processos)")
            current_columns_info = c.fetchall()
            current_column_names = [col[1] for col in current_columns_info]

            # Verifica se TODAS as colunas esperadas estão presentes
            if not all(col_name in current_column_names for col_name in expected_processos_column_names):
                schema_outdated = True
        else:
            schema_outdated = True # Tabela não existe, então precisa ser criada

        if schema_outdated:
            st.warning("⚠️ Detectada estrutura de banco de dados antiga ou inconsistente. Recriando tabelas...")
            c.execute('DROP TABLE IF EXISTS tramitacao')
            c.execute('DROP TABLE IF EXISTS analises')
            c.execute('DROP TABLE IF EXISTS processos')
            conn.commit() # Commit das drops

            # Recriar tabela 'processos'
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
            conn.commit() # Commit da criação da tabela processos

        # Criar tabela 'analises' (sempre garante que exista)
        c.execute('''CREATE TABLE IF NOT EXISTS analises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_id INTEGER NOT NULL,
            resultado TEXT NOT NULL,
            status TEXT NOT NULL,
            data_analise TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (processo_id) REFERENCES processos(id)
        )''')

        # Criar tabela 'tramitacao' (sempre garante que exista)
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
        return False, "❌ Erro: Já existe um processo com este número!"
    except Exception as e:
        return False, f"❌ Erro ao cadastrar: {str(e)}"

def atualizar(pid, numero, rt, requerente, analista, uso, tipologia, area, data_protocolo):
    """Atualiza um processo existente no banco de dados."""
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        c.execute('''UPDATE processos 
                    SET numero=?, rt=?, requerente=?, analista=?, uso=?, tipologia=?, area=?, data_protocolo=?
                    WHERE id=?''',
                 (numero, rt, requerente, analista, uso, tipologia, area, data_protocolo, pid))
        conn.commit()
        return True, "✅ Processo atualizado com sucesso!"
    except Exception as e:
        return False, f"❌ Erro ao atualizar processo: {str(e)}"

def deletar(pid):
    """Deleta um processo e suas tramitações/análises associadas."""
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        c.execute('DELETE FROM tramitacao WHERE processo_id=?', (pid,))
        c.execute('DELETE FROM analises WHERE processo_id=?', (pid,))
        c.execute('DELETE FROM processos WHERE id=?', (pid,))
        conn.commit()
        return True, "✅ Processo deletado com sucesso!"
    except Exception as e:
        return False, f"❌ Erro ao deletar processo: {str(e)}"

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

def registrar_tramitacao(processo_id, setor, data_entrada, data_saida=None, observacao=""):
    """Registra uma nova movimentação de tramitação para um processo."""
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        c.execute('''INSERT INTO tramitacao 
                    (processo_id, setor, data_entrada, data_saida, observacao) 
                    VALUES (?, ?, ?, ?, ?)''',
                 (processo_id, setor, data_entrada, data_saida, observacao))
        conn.commit()
        return True, "✅ Tramitação registrada com sucesso!"
    except Exception as e:
        return False, f"❌ Erro ao registrar tramitação: {str(e)}"

def listar_tramitacoes(processo_id):
    """Lista as tramitações de um processo específico."""
    if not conn: return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM tramitacao WHERE processo_id = ? ORDER BY data_entrada ASC', (processo_id,))
        return c.fetchall()
    except Exception as e:
        st.error(f"❌ Erro ao listar tramitações: {str(e)}")
        return []

def atualizar_tramitacao(tramitacao_id, setor, data_entrada, data_saida, observacao):
    """Atualiza uma tramitação existente."""
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        c.execute('''UPDATE tramitacao 
                    SET setor=?, data_entrada=?, data_saida=?, observacao=?
                    WHERE id=?''',
                 (setor, data_entrada, data_saida, observacao, tramitacao_id))
        conn.commit()
        return True, "✅ Tramitação atualizada com sucesso!"
    except Exception as e:
        return False, f"❌ Erro ao atualizar tramitação: {str(e)}"

def deletar_tramitacao(tramitacao_id):
    """Deleta uma tramitação específica."""
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        c.execute('DELETE FROM tramitacao WHERE id=?', (tramitacao_id,))
        conn.commit()
        return True, "✅ Tramitação deletada com sucesso!"
    except Exception as e:
        return False, f"❌ Erro ao deletar tramitação: {str(e)}"

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
        st.error(f"❌ Erro ao listar análises: {str(e)}")
        return []

def atualizar_status(processo_id, novo_status):
    """Atualiza o status de um processo."""
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        c.execute('UPDATE processos SET status = ? WHERE id = ?', (novo_status, processo_id))
        conn.commit()
        return True, "✅ Status atualizado!"
    except Exception as e:
        return False, f"❌ Erro ao atualizar status: {str(e)}"

def get_processos_df():
    """Carrega todos os processos para um DataFrame do pandas."""
    if not conn: return pd.DataFrame()
    try:
        df = pd.read_sql_query("SELECT * FROM processos", conn)
        # Converte colunas de data para datetime, com 'coerce' para lidar com erros
        df['data_protocolo'] = pd.to_datetime(df['data_protocolo'], errors='coerce')
        df['data_cadastro'] = pd.to_datetime(df['data_cadastro'], errors='coerce')
        return df
    except Exception as e:
        st.error(f"❌ Erro ao carregar processos para DataFrame: {e}")
        return pd.DataFrame()

def get_tramitacoes_df():
    """Carrega todas as tramitações para um DataFrame do pandas."""
    if not conn: return pd.DataFrame()
    try:
        df = pd.read_sql_query("SELECT * FROM tramitacao", conn)
        df['data_entrada'] = pd.to_datetime(df['data_entrada'], errors='coerce')
        df['data_saida'] = pd.to_datetime(df['data_saida'], errors='coerce')
        # Calcula a duração em dias, lidando com NaT (Not a Time) se data_saida for nula
        df['duracao_dias'] = (df['data_saida'] - df['data_entrada']).dt.days.fillna(0)
        return df
    except Exception as e:
        st.error(f"❌ Erro ao carregar tramitações para DataFrame: {e}")
        return pd.DataFrame()

# ==================== SIDEBAR ====================
with st.sidebar:
    st.image("https://www.contagem.mg.gov.br/portal/uploads/2023/07/logo-contagem-2023.png", width=200)
    st.title("⚙️ Configurações")

    # Botão de Resetar Banco de Dados no topo da sidebar
    if st.button("🔄 Resetar Banco de Dados", help="Apaga todos os dados e recria as tabelas. Use com cautela!", type="secondary"):
        reset_database()

    st.subheader("🔑 Chave de API Google Gemini")
    # Usa st.session_state['api_key'] como valor padrão
    api_key_input = st.text_input("Insira sua API Key:", type="password", value=st.session_state['api_key'])
    if api_key_input:
        st.session_state['api_key'] = api_key_input
        st.success("API Key configurada!")
    else:
        st.warning("Por favor, insira sua API Key do Google Gemini para usar a análise de IA.")

    st.divider()
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center'>
        <p><strong>Desenvolvido por Dayane</strong></p>
        <p>Versão 1.0.0</p>
    </div>
    """, unsafe_allow_html=True)

# ==================== ABAS PRINCIPAIS ====================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["➕ Cadastrar", "📋 Gerenciar", "🔄 Tramitação", "📊 Kanban", "🤖 Analisar", "📈 Gráficos"])

# Opções para os campos de seleção
usos_options = ["Unifamiliar", "Multifamiliar", "Serviços", "Comércio Varejista", "Comércio Atacadista", "Indústria", "Misto", "Sem destinação específica"]
tipologias_options = ["Aprovação Inicial", "Levantamento Existente", "Modificação de Projeto", "Regularização", "Misto", "RIU", "ERB", "As Built"]
setores_tramitacao = ["Protocolo", "Requerente", "Analista", "Fiscalização", "Parecer Externo", "Emissão de Alvará", "Arquivo"]
status_kanban = ["Protocolado", "Em Análise", "Aguardando Correções", "Aprovado", "Reprovado"]

# ==================== ABA 1: CADASTRAR ====================
with tab1:
    st.header("➕ Cadastrar Novo Processo")

    with st.form("cadastro_processo"):
        col1, col2 = st.columns(2)
        with col1:
            numero = st.text_input("Número do Processo", help="Ex: 12345/2024", required=True)
            rt = st.text_input("Responsável Técnico (RT)", required=True)
            requerente = st.text_input("Nome do Requerente", required=True)
            analista = st.text_input("Nome do Analista Responsável", required=True)
        with col2:
            uso = st.selectbox("Uso", usos_options, required=True)
            tipologia = st.selectbox("Tipologia", tipologias_options, required=True)
            area = st.number_input("Área Construída (m²)", min_value=0.0, value=0.0, step=0.01, required=True)
            data_protocolo = st.date_input("Data do Protocolo", value="today", required=True)

        st.divider()
        submit_button = st.form_submit_button("Salvar Processo", type="primary", use_container_width=True)

        if submit_button:
            if numero and rt and requerente and analista and uso and tipologia and area is not None and data_protocolo:
                sucesso, msg = cadastrar(numero, rt, requerente, analista, uso, tipologia, area, data_protocolo.strftime('%Y-%m-%d'))
                if sucesso:
                    st.success(msg)
                    st.experimental_rerun() # Recarrega para atualizar a lista
                else:
                    st.error(msg)
            else:
                st.error("❌ Por favor, preencha todos os campos obrigatórios.")

# ==================== ABA 2: GERENCIAR ====================
with tab2:
    st.header("📋 Gerenciar Processos")

    processos = listar()

    if not processos:
        st.info("📭 Nenhum processo cadastrado ainda.")
    else:
        st.subheader(f"Total de Processos: {len(processos)}")
        for p in processos:
            # p: (id, numero, rt, requerente, analista, uso, tipologia, area, data_protocolo, status, data_cadastro)
            with st.expander(f"Processo: {p[1]} - Requerente: {p[3]} - Status: {p[9]}"):
                st.markdown(f"**Número:** {p[1]}")
                st.markdown(f"**RT:** {p[2]}")
                st.markdown(f"**Requerente:** {p[3]}")
                st.markdown(f"**Analista:** {p[4]}")
                st.markdown(f"**Uso:** {p[5]}")
                st.markdown(f"**Tipologia:** {p[6]}")
                st.markdown(f"**Área:** {p[7]} m²")
                st.markdown(f"**Data Protocolo:** {datetime.strptime(p[8], '%Y-%m-%d').strftime('%d/%m/%Y')}")
                st.markdown(f"**Status:** {p[9]}")
                st.markdown(f"**Cadastrado em:** {datetime.strptime(p[10], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')}")

                col_edit, col_del = st.columns(2)

                with col_edit:
                    if st.button("✏️ Editar Processo", key=f"edit_{p[0]}", use_container_width=True):
                        st.session_state[f"edit_mode_{p[0]}"] = not st.session_state.get(f"edit_mode_{p[0]}", False)

                with col_del:
                    if st.button("🗑️ Deletar Processo", key=f"delete_{p[0]}", type="secondary", use_container_width=True):
                        # Confirmação de deleção
                        if st.warning(f"Tem certeza que deseja deletar o processo {p[1]}? Esta ação é irreversível e também apagará todas as tramitações e análises associadas."):
                            if st.button("CONFIRMAR DELEÇÃO", key=f"confirm_delete_{p[0]}", type="danger"):
                                sucesso, msg = deletar(p[0])
                                if sucesso:
                                    st.success(msg)
                                    st.experimental_rerun()
                                else:
                                    st.error(msg)

                if st.session_state.get(f"edit_mode_{p[0]}", False):
                    st.subheader(f"✏️ Editando Processo {p[1]}")
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

                        ed_area = st.number_input("Área (m²)", value=float(p[7]), min_value=0.0, key=f"ed_area_{p[0]}")

                        try:
                            default_date_protocolo = datetime.strptime(p[8], '%Y-%m-%d').date()
                        except (ValueError, TypeError):
                            default_date_protocolo = datetime.now().date()
                        ed_data_protocolo = st.date_input("Data do Protocolo", value=default_date_protocolo, key=f"ed_data_protocolo_{p[0]}")

                        if st.form_submit_button("Salvar Alterações", type="primary"):
                            sucesso, msg = atualizar(p[0], ed_numero, ed_rt, ed_requerente, ed_analista, ed_uso, ed_tipologia, ed_area, ed_data_protocolo.strftime('%Y-%m-%d'))
                            if sucesso:
                                st.success(msg)
                                st.session_state[f"edit_mode_{p[0]}"] = False # Sai do modo de edição
                                st.experimental_rerun()
                            else:
                                st.error(msg)

# ==================== ABA 3: TRAMITAÇÃO ====================
with tab3:
    st.header("🔄 Gerenciar Tramitação de Processos")

    processos_tramitacao = listar()
    if not processos_tramitacao:
        st.info("📭 Nenhum processo cadastrado para gerenciar tramitação.")
    else:
        processo_selecionado_id = st.selectbox(
            "Selecione o Processo para Tramitação:",
            options=[(p[0], p[1]) for p in processos_tramitacao],
            format_func=lambda x: f"{x[1]}",
            key="select_processo_tramitacao"
        )

        if processo_selecionado_id:
            pid_tramitacao = processo_selecionado_id[0]
            st.subheader(f"Movimentações do Processo: {processo_selecionado_id[1]}")

            # Formulário para registrar nova tramitação
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
                    if data_entrada_nova:
                        # Primeiro, fechar a tramitação anterior se houver uma aberta
                        c = conn.cursor()
                        c.execute('''UPDATE tramitacao 
                                    SET data_saida = ? 
                                    WHERE processo_id = ? AND data_saida IS NULL''', 
                                 (data_entrada_nova.strftime('%Y-%m-%d'), pid_tramitacao))
                        conn.commit()

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
                    else:
                        st.error("❌ A Data de Entrada é obrigatória.")

            st.divider()
            st.markdown("#### Histórico de Tramitação")
            tramitacoes = listar_tramitacoes(pid_tramitacao)

            if not tramitacoes:
                st.info("📭 Nenhuma movimentação registrada para este processo.")
            else:
                # Calcular tempo em cada setor
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
                    elif i == len(tramitacoes) - 1: # Se for a última e não tem data de saída, usa até hoje
                        duracao = (datetime.now() - data_entrada).days
                        tempos_por_setor[setor] = tempos_por_setor.get(setor, 0) + duracao

                st.markdown("##### ⏱️ Tempo Acumulado por Setor:")
                cols_metrics = st.columns(len(setores_tramitacao))
                for idx, setor in enumerate(setores_tramitacao):
                    with cols_metrics[idx]:
                        st.metric(setor, f"{tempos_por_setor.get(setor, 0)} dias")

                st.divider()

                for t in tramitacoes:
                    # t: (id, processo_id, setor, data_entrada, data_saida, observacao)
                    icon = "➡️"
                    if t[2] == "Protocolo": icon = "📝"
                    elif t[2] == "Requerente": icon = "👤"
                    elif t[2] == "Analista": icon = "👨‍💻"
                    elif t[2] == "Fiscalização": icon = "🔍"
                    elif t[2] == "Parecer Externo": icon = "🏢"
                    elif t[2] == "Emissão de Alvará": icon = "📜"
                    elif t[2] == "Arquivo": icon = "🗄️"

                    data_saida_display = datetime.strptime(t[4], '%Y-%m-%d').strftime('%d/%m/%Y') if t[4] else "Em andamento"

                    with st.expander(f"{icon} {t[2]} - Entrada: {datetime.strptime(t[3], '%Y-%m-%d').strftime('%d/%m/%Y')} - Saída: {data_saida_display}"):
                        st.markdown(f"**Setor:** {t[2]}")
                        st.markdown(f"**Data de Entrada:** {datetime.strptime(t[3], '%Y-%m-%d').strftime('%d/%m/%Y')}")
                        st.markdown(f"**Data de Saída:** {data_saida_display}")
                        st.markdown(f"**Observações:** {t[5] if t[5] else 'Nenhuma'}")

                        col_tedit, col_tdel = st.columns(2)
                        with col_tedit:
                            if st.button("✏️ Editar Movimentação", key=f"edit_tram_{t[0]}", use_container_width=True):
                                st.session_state[f"edit_tram_mode_{t[0]}"] = not st.session_state.get(f"edit_tram_mode_{t[0]}", False)
                        with col_tdel:
                            if st.button("🗑️ Deletar Movimentação", key=f"delete_tram_{t[0]}", type="secondary", use_container_width=True):
                                # Confirmação de deleção
                                if st.warning(f"Tem certeza que deseja deletar esta movimentação ({t[2]})?"):
                                    if st.button("CONFIRMAR DELEÇÃO", key=f"confirm_delete_tram_{t[0]}", type="danger"):
                                        sucesso, msg = deletar_tramitacao(t[0])
                                        if sucesso:
                                            st.success(msg)
                                            st.experimental_rerun()
                                        else:
                                            st.error(msg)

                        if st.session_state.get(f"edit_tram_mode_{t[0]}", False):
                            st.markdown("##### Editando Movimentação")
                            with st.form(f"form_editar_tramitacao_{t[0]}"):
                                ed_setor = st.selectbox("Setor", setores_tramitacao, index=setores_tramitacao.index(t[2]), key=f"ed_setor_{t[0]}")
                                ed_data_entrada = st.date_input("Data de Entrada", value=datetime.strptime(t[3], '%Y-%m-%d').date(), key=f"ed_data_entrada_{t[0]}")
                                ed_data_saida_val = datetime.strptime(t[4], '%Y-%m-%d').date() if t[4] else None
                                ed_data_saida = st.date_input("Data de Saída", value=ed_data_saida_val, key=f"ed_data_saida_{t[0]}")
                                ed_observacao = st.text_area("Observações", value=t[5], key=f"ed_observacao_{t[0]}")

                                if st.form_submit_button("Salvar Alterações da Movimentação", type="primary"):
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

# ==================== ABA 4: KANBAN ====================
with tab4:
    st.header("📊 Quadro Kanban de Processos")

    processos_kanban = listar()

    if not processos_kanban:
        st.info("📭 Nenhum processo cadastrado para exibir no Kanban.")
    else:
        # Organiza os processos por status
        processos_por_status = {status: [] for status in status_kanban}
        for p in processos_kanban:
            processos_por_status[p[9]].append(p) # p[9] é o status

        cols = st.columns(len(status_kanban))

        for i, status in enumerate(status_kanban):
            with cols[i]:
                st.subheader(f"{status} ({len(processos_por_status[status])})")
                st.markdown("---")

                for p in processos_por_status[status]:
                    # p: (id, numero, rt, requerente, analista, uso, tipologia, area, data_protocolo, status, data_cadastro)
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

                    # Botões para mudar status
                    current_status_index = status_kanban.index(status)

                    if current_status_index > 0: # Não pode mover para "anterior" se já é o primeiro
                        if st.button(f"⬅️ Mover para {status_kanban[current_status_index-1]}", key=f"move_prev_{p[0]}"):
                            sucesso, msg = atualizar_status(p[0], status_kanban[current_status_index-1])
                            if sucesso: st.experimental_rerun()
                            else: st.error(msg)

                    if current_status_index < len(status_kanban) - 1: # Não pode mover para "próximo" se já é o último
                        if st.button(f"➡️ Mover para {status_kanban[current_status_index+1]}", key=f"move_next_{p[0]}"):
                            sucesso, msg = atualizar_status(p[0], status_kanban[current_status_index+1])
                            if sucesso: st.experimental_rerun()
                            else: st.error(msg)
                    st.markdown("---") # Separador entre cards

# ==================== ABA 5: ANALISAR ====================
with tab5:
    st.header("🤖 Análise de Projetos com IA")

    if not st.session_state['api_key']: # Verifica a API Key da sidebar
        st.warning("⚠️ Configure sua API Key do Google Gemini na barra lateral para usar esta função.")
        st.info("**Como obter:** Acesse https://aistudio.google.com/app/apikey e crie uma chave gratuita.")
        st.stop()

    processos_analise = listar()
    if not processos_analise:
        st.info("📭 Nenhum processo cadastrado para análise.")
    else:
        processo_selecionado_analise = st.selectbox(
            "Selecione o Processo para Análise:",
            options=[(p[0], p[1]) for p in processos_analise],
            format_func=lambda x: f"{x[1]} - {buscar_por_numero(x[1])[3]}", # Exibe número e requerente
            key="select_processo_analise"
        )

        if processo_selecionado_analise:
            pid_analise = processo_selecionado_analise[0]
            dados = buscar_por_numero(processo_selecionado_analise[1]) # Busca todos os dados do processo

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

                                # Extrair texto dos PDFs do projeto
                                txt_proj = ""
                                for pdf in proj:
                                    reader = PyPDF2.PdfReader(pdf)
                                    for page in reader.pages:
                                        txt_proj += page.extract_text() + "\n"

                                # Extrair texto dos PDFs da legislação
                                txt_leg = ""
                                for pdf in leg:
                                    reader = PyPDF2.PdfReader(pdf)
                                    for page in reader.pages:
                                        txt_leg += page.extract_text() + "\n"

                                # Tentar criar modelo (prioriza modelos mais avançados)
                                model = None
                                for nome in ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']:
                                    try:
                                        model = genai.GenerativeModel(nome)
                                        st.info(f"✅ Usando modelo: {nome}")
                                        break
                                    except Exception as e:
                                        # st.warning(f"Modelo {nome} não disponível ou erro: {e}")
                                        continue

                                if not model:
                                    st.error("❌ Nenhum modelo do Gemini disponível. Verifique sua API Key e a disponibilidade dos modelos.")
                                    st.stop()

                                # Criar prompt para análise
                                prompt = f"""Você é um analista técnico especializado em projetos arquitetônicos da Prefeitura de Contagem - MG.

**DADOS DO PROCESSO:**
- Número: {dados[1]}
- RT: {dados[2]}
- Requerente: {dados[3]}
- Analista: {dados[4]}
- Uso: {dados[5]}
- Tipologia: {dados[6]}
- Área: {dados[7]}m²
- Data do Protocolo: {datetime.strptime(dados[8], '%Y-%m-%d').strftime('%d/%m/%Y')}
- Status Atual: {dados[9]}

**LEGISLAÇÃO MUNICIPAL APLICÁVEL:**
{txt_leg[:4000]}

**REGRAS ESPECÍFICAS A VERIFICAR:**
{regras}

**PROJETO ARQUITETÔNICO SUBMETIDO:**
{txt_proj[:6000]}

**INSTRUÇÕES PARA ANÁLISE:**
Analise detalhadamente o projeto arquitetônico e verifique sua conformidade com a legislação municipal de Contagem.

**IMPORTANTE:**
- SEMPRE cite o artigo específico da lei.
- Seja técnico, objetivo e preciso.
- Identifique problemas com localização no projeto quando possível.
- Use linguagem formal de parecer técnico.

**FORMATO DA RESPOSTA:**

## ✅ CONFORMIDADES
(liste o que está conforme, citando artigos)

## ❌ NÃO CONFORMIDADES - PONTOS A CORRIGIR
(para cada violação: artigo violado, problema, localização no projeto, correção necessária)

## ⚠️ PONTOS DE ATENÇÃO
(itens que necessitam verificação presencial ou documentação complementar)

## 🔧 RECOMENDAÇÕES TÉCNICAS
(sugestões detalhadas para correção)

## 📊 PARECER TÉCNICO FINAL
Emita parecer conclusivo: **APROVADO** ou **REPROVADO** (justifique tecnicamente citando artigos).
"""

                                # Gerar análise
                                resposta = model.generate_content(prompt)

                                # Determinar status
                                texto_resposta = resposta.text.upper()
                                status_analise = "INCONCLUSIVO"
                                if "APROVADO" in texto_resposta and "REPROVADO" not in texto_resposta:
                                    status_analise = "APROVADO"
                                    st.success("✅ PROJETO APROVADO")
                                    atualizar_status(dados[0], "Aprovado") # Atualiza status no processo
                                elif "REPROVADO" in texto_resposta:
                                    status_analise = "REPROVADO"
                                    st.error("❌ PROJETO REPROVADO")
                                    atualizar_status(dados[0], "Reprovado") # Atualiza status no processo
                                else:
                                    st.warning("⚠️ ANÁLISE INCONCLUSIVA")
                                    atualizar_status(dados[0], "Em Análise") # Mantém ou define como Em Análise

                                st.divider()

                                # Exibir resultado
                                st.markdown(resposta.text)

                                # Salvar análise no banco
                                salvar_analise(dados[0], resposta.text, status_analise)

                                # Preparar relatório para download
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

                                # Botão de download
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

    # Converte a lista de processos em um DataFrame do pandas
    # As colunas devem corresponder à ordem do SELECT * na função listar()
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
            # Filtra linhas com data_protocolo válida
            df_valid_dates = procs_df.dropna(subset=['data_protocolo'])
            if not df_valid_dates.empty:
                # Agrupa por data de protocolo e conta
                df_grouped = df_valid_dates.groupby(df_valid_dates['data_protocolo'].dt.to_period('M')).size().reset_index(name='Quantidade')
                df_grouped['data_protocolo'] = df_grouped['data_protocolo'].dt.to_timestamp() # Converte para timestamp para Plotly

                fig = px.line(df_grouped, x='data_protocolo', y='Quantidade', 
                              title='Processos Protocolados por Mês',
                              labels={'data_protocolo': 'Mês de Protocolo', 'Quantidade': 'Número de Processos'},
                              template='plotly_white')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Nenhum processo com data de protocolo válida para este gráfico.")


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

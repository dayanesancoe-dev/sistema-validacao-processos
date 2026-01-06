import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime, timedelta
import sqlite3
import os
import pandas as pd # Importar pandas para manipulação de dados
import plotly.express as px # Importar plotly para gráficos

st.set_page_config(page_title="Sistema de Validação", page_icon="🏛️", layout="wide")

# ==================== BANCO DE DADOS ====================

def reset_database():
    """Reseta o banco de dados, removendo o arquivo e limpando o cache."""
    try:
        if os.path.exists('processos.db'):
            os.remove('processos.db')
        st.cache_resource.clear() # Limpa o cache para forçar a recriação da conexão
        st.success("✅ Banco de dados resetado com sucesso! Recarregue a página.")
        st.stop() # Para a execução para que o usuário possa recarregar
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
        expected_processos_columns = [
            'id', 'numero', 'rt', 'requerente', 'analista', 'uso', 
            'tipologia', 'area', 'data_protocolo', 'status', 'data_cadastro'
        ]

        if table_exists:
            # Verificar o schema atual da tabela 'processos'
            c.execute("PRAGMA table_info(processos)")
            current_columns_info = c.fetchall()
            current_column_names = [col[1] for col in current_columns_info]

            # Se o número de colunas não corresponde ou uma coluna chave está faltando, recriar
            if len(current_column_names) != len(expected_processos_columns) or \
               'data_protocolo' not in current_column_names or \
               'status' not in current_column_names:

                st.warning("⚠️ Detectada estrutura de banco de dados antiga ou inconsistente. Recriando tabelas...")
                c.execute('DROP TABLE IF EXISTS tramitacao')
                c.execute('DROP TABLE IF EXISTS analises')
                c.execute('DROP TABLE IF EXISTS processos')
                conn.commit() # Commit as drops antes de criar as novas
                table_exists = False # Força a criação das tabelas abaixo

        # Criar tabela 'processos' (se não existia ou foi recriada)
        if not table_exists:
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

        # Criar tabela 'analises'
        c.execute('''CREATE TABLE IF NOT EXISTS analises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_id INTEGER NOT NULL,
            resultado TEXT NOT NULL,
            status TEXT NOT NULL,
            data_analise TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (processo_id) REFERENCES processos(id)
        )''')

        # Criar tabela 'tramitacao'
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
        return False, f"❌ Erro ao cadastrar processo: {str(e)}"

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
    except Exception as e:
        return False, f"❌ Erro ao atualizar processo: {str(e)}"

def atualizar_status(pid, novo_status):
    """Atualiza o status de um processo."""
    if not conn: return False
    try:
        c = conn.cursor()
        c.execute('UPDATE processos SET status = ? WHERE id = ?', (novo_status, pid))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar status: {e}")
        return False

def listar():
    """Lista todos os processos."""
    if not conn: return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM processos ORDER BY id DESC')
        return c.fetchall()
    except Exception as e:
        st.error(f"Erro ao listar processos: {e}")
        return []

def listar_por_status(status):
    """Lista processos por um status específico."""
    if not conn: return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM processos WHERE status = ? ORDER BY id DESC', (status,))
        return c.fetchall()
    except Exception as e:
        st.error(f"Erro ao listar processos por status: {e}")
        return []

def buscar_por_numero(numero):
    """Busca um processo pelo número."""
    if not conn: return None
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM processos WHERE numero = ?', (numero,))
        return c.fetchone()
    except Exception as e:
        st.error(f"Erro ao buscar processo por número: {e}")
        return None

def deletar(pid):
    """Deleta um processo e suas análises/tramitações associadas."""
    if not conn: return False
    try:
        c = conn.cursor()
        c.execute('DELETE FROM analises WHERE processo_id = ?', (pid,))
        c.execute('DELETE FROM tramitacao WHERE processo_id = ?', (pid,))
        c.execute('DELETE FROM processos WHERE id = ?', (pid,))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao deletar processo: {e}")
        return False

def salvar_analise(pid, resultado, status):
    """Salva o resultado de uma análise no banco de dados."""
    if not conn: return False
    try:
        c = conn.cursor()
        c.execute('INSERT INTO analises (processo_id, resultado, status) VALUES (?, ?, ?)', 
                 (pid, resultado, status))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar análise: {e}")
        return False

def buscar_analises(pid):
    """Busca todas as análises de um processo."""
    if not conn: return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM analises WHERE processo_id = ? ORDER BY id DESC', (pid,))
        return c.fetchall()
    except Exception as e:
        st.error(f"Erro ao buscar análises: {e}")
        return []

def adicionar_tramitacao(processo_id, setor, data_entrada, observacao=""):
    """Adiciona uma nova movimentação de tramitação para um processo."""
    if not conn: return False
    try:
        c = conn.cursor()
        # Primeiro, fechar a tramitação anterior se houver uma aberta
        c.execute('''UPDATE tramitacao 
                    SET data_saida = ? 
                    WHERE processo_id = ? AND data_saida IS NULL''', 
                 (data_entrada, processo_id))

        # Adicionar a nova tramitação
        c.execute('''INSERT INTO tramitacao 
                    (processo_id, setor, data_entrada, observacao) 
                    VALUES (?, ?, ?, ?)''',
                 (processo_id, setor, data_entrada, observacao))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar tramitação: {e}")
        return False

def atualizar_tramitacao(tid, setor, data_entrada, data_saida, observacao):
    """Atualiza uma movimentação de tramitação existente."""
    if not conn: return False
    try:
        c = conn.cursor()
        c.execute('''UPDATE tramitacao 
                    SET setor=?, data_entrada=?, data_saida=?, observacao=?
                    WHERE id=?''',
                 (setor, data_entrada, data_saida, observacao, tid))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar tramitação: {e}")
        return False

def deletar_tramitacao(tid):
    """Deleta uma movimentação de tramitação."""
    if not conn: return False
    try:
        c = conn.cursor()
        c.execute('DELETE FROM tramitacao WHERE id = ?', (tid,))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao deletar tramitação: {e}")
        return False

def buscar_tramitacoes(processo_id):
    """Busca todas as tramitações de um processo."""
    if not conn: return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM tramitacao WHERE processo_id = ? ORDER BY data_entrada ASC', (processo_id,))
        return c.fetchall()
    except Exception as e:
        st.error(f"Erro ao buscar tramitações: {e}")
        return []

def calcular_tempo_setores(tramitacoes):
    """Calcula o tempo em dias que o processo ficou em cada setor."""
    tempos_setores = {}
    for i, t in enumerate(tramitacoes):
        setor = t[2]
        data_entrada_str = t[3]
        data_saida_str = t[4]

        data_entrada = datetime.strptime(data_entrada_str, '%Y-%m-%d %H:%M:%S')

        if data_saida_str:
            data_saida = datetime.strptime(data_saida_str, '%Y-%m-%d %H:%M:%S')
        else:
            # Se for a última tramitação e não tem data de saída, usa a data atual
            if i == len(tramitacoes) - 1:
                data_saida = datetime.now()
            else:
                data_saida = data_entrada # Ou outra lógica, dependendo do que significa 'sem data de saída'

        duracao = (data_saida - data_entrada).days
        tempos_setores[setor] = tempos_setores.get(setor, 0) + duracao
    return tempos_setores

# Funções para carregar dados em DataFrames para gráficos
def get_processos_df():
    """Carrega todos os processos em um DataFrame do pandas."""
    if not conn: return pd.DataFrame()
    try:
        df = pd.read_sql_query("SELECT * FROM processos", conn)
        df['data_protocolo'] = pd.to_datetime(df['data_protocolo'])
        df['data_cadastro'] = pd.to_datetime(df['data_cadastro'])
        return df
    except Exception as e:
        st.error(f"Erro ao carregar processos para DataFrame: {e}")
        return pd.DataFrame()

def get_tramitacoes_df():
    """Carrega todas as tramitações em um DataFrame do pandas e calcula a duração."""
    if not conn: return pd.DataFrame()
    try:
        df = pd.read_sql_query("SELECT * FROM tramitacao", conn)
        df['data_entrada'] = pd.to_datetime(df['data_entrada'])
        df['data_saida'] = pd.to_datetime(df['data_saida'])
        df['duracao_dias'] = (df['data_saida'] - df['data_entrada']).dt.days.fillna(0) # Duração em dias
        return df
    except Exception as e:
        st.error(f"Erro ao carregar tramitações para DataFrame: {e}")
        return pd.DataFrame()

# ==================== SIDEBAR ====================
with st.sidebar:
    st.title("⚙️ Configurações")
    api_key = st.text_input("API Key Google Gemini:", type="password", 
                            help="Cole sua API Key do Google Gemini aqui. Obtenha em https://aistudio.google.com/app/apikey")
    if api_key:
        st.session_state['api_key'] = api_key
        st.success("API Key configurada!")
    else:
        st.session_state['api_key'] = None
        st.warning("API Key não configurada.")

    st.divider()
    if st.button("🔄 Resetar Banco de Dados", help="Apaga todos os dados e recria as tabelas. Use com cautela!"):
        reset_database()

# ==================== ABAS PRINCIPAIS ====================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "➕ Cadastrar", "📋 Gerenciar", "➡️ Tramitação", "📊 Kanban", "🤖 Analisar", "📈 Dashboard & Relatórios"
])

# ==================== ABA 1: CADASTRAR ====================
with tab1:
    st.header("➕ Cadastrar Novo Processo")

    with st.form("cadastro_processo"):
        numero = st.text_input("Número do Processo:", placeholder="Ex: 12345/2023", key="cad_numero")
        rt = st.text_input("RT (Responsável Técnico):", placeholder="Ex: Arq. João Silva - CAU A123456", key="cad_rt")
        requerente = st.text_input("Requerente:", placeholder="Ex: Maria Oliveira", key="cad_requerente")
        analista = st.text_input("Analista Responsável:", placeholder="Ex: Ana Paula", key="cad_analista")

        col1, col2 = st.columns(2)
        with col1:
            uso = st.selectbox("Uso:", 
                               ['Unifamiliar', 'Multifamiliar', 'Serviços', 'Comércio Varejista', 
                                'Comércio Atacadista', 'Indústria', 'Misto', 'Sem destinação específica'], 
                               key="cad_uso")
        with col2:
            tipologia = st.selectbox("Tipologia:", 
                                     ['Aprovação Inicial', 'Levantamento Existente', 'Modificação de Projeto', 
                                      'Regularização', 'Misto', 'RIU', 'ERB', 'As Built'], 
                                     key="cad_tipologia")

        area = st.number_input("Área (m²):", min_value=0.0, format="%.2f", key="cad_area")
        data_protocolo = st.date_input("Data do Protocolo:", value="today", key="cad_data_protocolo")

        submitted = st.form_submit_button("✅ Cadastrar Processo", type="primary")
        if submitted:
            if numero and rt and requerente and analista and uso and tipologia and area is not None and data_protocolo:
                data_protocolo_str = data_protocolo.strftime('%Y-%m-%d')
                success, msg = cadastrar(numero, rt, requerente, analista, uso, tipologia, area, data_protocolo_str)
                if success:
                    st.success(msg)
                    # Adiciona a primeira tramitação automaticamente
                    adicionar_tramitacao(buscar_por_numero(numero)[0], "Protocolo", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    st.info("Primeira tramitação (Protocolo) registrada automaticamente.")
                else:
                    st.error(msg)
            else:
                st.error("❌ Preencha todos os campos!")

# ==================== ABA 2: GERENCIAR ====================
with tab2:
    st.header("📋 Gerenciar Processos Existentes")

    procs = listar()

    if not procs:
        st.info("📭 Nenhum processo cadastrado ainda.")
    else:
        for p in procs:
            # p[0]=id, p[1]=numero, p[2]=rt, p[3]=requerente, p[4]=analista, p[5]=uso, p[6]=tipologia, p[7]=area, p[8]=data_protocolo, p[9]=status, p[10]=data_cadastro

            with st.expander(f"📄 **{p[1]}** - {p[3]} ({p[9]})"):
                st.write(f"**RT:** {p[2]}")
                st.write(f"**Requerente:** {p[3]}")
                st.write(f"**Analista:** {p[4]}")
                st.write(f"**Uso:** {p[5]} | **Tipologia:** {p[6]}")
                st.write(f"**Área:** {p[7]}m²")
                st.write(f"**Data Protocolo:** {datetime.strptime(p[8], '%Y-%m-%d').strftime('%d/%m/%Y')}")
                st.markdown(f"**Cadastrado em:** {datetime.strptime(p[10], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')}")

                st.divider()

                # Botões de Ação
                col_edit, col_del = st.columns(2)
                with col_edit:
                    if st.button("✏️ Editar Cadastro", key=f"edit_proc_{p[0]}", use_container_width=True):
                        st.session_state[f"edit_proc_form_{p[0]}"] = True
                with col_del:
                    if st.button("🗑️ Deletar Processo", key=f"del_proc_{p[0]}", use_container_width=True, type="secondary"):
                        if deletar(p[0]):
                            st.success(f"✅ Processo {p[1]} deletado!")
                            st.rerun()
                        else:
                            st.error(f"❌ Erro ao deletar processo {p[1]}.")

                # Formulário de Edição (aparece ao clicar em Editar)
                if st.session_state.get(f"edit_proc_form_{p[0]}", False):
                    st.subheader(f"Editar Processo {p[1]}")
                    with st.form(f"form_edit_proc_{p[0]}"):
                        ed_numero = st.text_input("Número do Processo:", value=p[1], key=f"ed_numero_{p[0]}")
                        ed_rt = st.text_input("RT:", value=p[2], key=f"ed_rt_{p[0]}")
                        ed_requerente = st.text_input("Requerente:", value=p[3], key=f"ed_requerente_{p[0]}")
                        ed_analista = st.text_input("Analista:", value=p[4], key=f"ed_analista_{p[0]}")

                        col_ed1, col_ed2 = st.columns(2)
                        with col_ed1:
                            ed_uso = st.selectbox("Uso:", 
                                                  ['Unifamiliar', 'Multifamiliar', 'Serviços', 'Comércio Varejista', 
                                                   'Comércio Atacadista', 'Indústria', 'Misto', 'Sem destinação específica'], 
                                                  index=['Unifamiliar', 'Multifamiliar', 'Serviços', 'Comércio Varejista', 
                                                         'Comércio Atacadista', 'Indústria', 'Misto', 'Sem destinação específica'].index(p[5]), 
                                                  key=f"ed_uso_{p[0]}")
                        with col_ed2:
                            ed_tipologia = st.selectbox("Tipologia:", 
                                                        ['Aprovação Inicial', 'Levantamento Existente', 'Modificação de Projeto', 
                                                         'Regularização', 'Misto', 'RIU', 'ERB', 'As Built'], 
                                                        index=['Aprovação Inicial', 'Levantamento Existente', 'Modificação de Projeto', 
                                                               'Regularização', 'Misto', 'RIU', 'ERB', 'As Built'].index(p[6]), 
                                                        key=f"ed_tipologia_{p[0]}")

                        ed_area = st.number_input("Área (m²):", value=float(p[7]), min_value=0.0, format="%.2f", key=f"ed_area_{p[0]}")
                        ed_data_protocolo = st.date_input("Data do Protocolo:", value=datetime.strptime(p[8], '%Y-%m-%d').date(), key=f"ed_data_protocolo_{p[0]}")

                        col_ed_btn1, col_ed_btn2 = st.columns(2)
                        with col_ed_btn1:
                            if st.form_submit_button("💾 Salvar Edição", type="primary", key=f"save_edit_proc_{p[0]}"):
                                ed_data_protocolo_str = ed_data_protocolo.strftime('%Y-%m-%d')
                                success, msg = atualizar(p[0], ed_numero, ed_rt, ed_requerente, ed_analista, ed_uso, ed_tipologia, ed_area, ed_data_protocolo_str)
                                if success:
                                    st.success(msg)
                                    st.session_state[f"edit_proc_form_{p[0]}"] = False # Fecha o formulário
                                    st.rerun()
                                else:
                                    st.error(msg)
                        with col_ed_btn2:
                            if st.form_submit_button("↩️ Cancelar", key=f"cancel_edit_proc_{p[0]}"):
                                st.session_state[f"edit_proc_form_{p[0]}"] = False # Fecha o formulário
                                st.rerun()

# ==================== ABA 3: TRAMITAÇÃO ====================
with tab3:
    st.header("➡️ Gerenciar Tramitação de Processos")

    procs_tram = listar()
    if not procs_tram:
        st.info("📭 Nenhum processo para tramitar. Cadastre um primeiro.")
        st.stop()

    proc_sel_tram = st.selectbox("Selecione o Processo:", 
                                 [f"{p[1]} - {p[3]}" for p in procs_tram], 
                                 key="sel_proc_tram")

    if proc_sel_tram:
        num_proc_tram = proc_sel_tram.split(" - ")[0]
        dados_tram = buscar_por_numero(num_proc_tram)

        if dados_tram:
            st.subheader(f"Movimentações do Processo: {dados_tram[1]}")

            # Formulário para adicionar nova tramitação
            with st.form(f"add_tramitacao_form_{dados_tram[0]}"):
                st.write("Adicionar Nova Movimentação:")
                setores_disponiveis = ['Protocolo', 'Requerente', 'Analista', 'Fiscalização', 
                                       'Parecer Externo', 'Emissão de Alvará', 'Arquivo']
                novo_setor = st.selectbox("Setor:", setores_disponiveis, key=f"novo_setor_{dados_tram[0]}")
                data_entrada_nova = st.date_input("Data de Entrada:", value="today", key=f"data_entrada_nova_{dados_tram[0]}")
                hora_entrada_nova = st.time_input("Hora de Entrada:", value=datetime.now().time(), key=f"hora_entrada_nova_{dados_tram[0]}")
                observacao_nova = st.text_area("Observação:", key=f"obs_nova_{dados_tram[0]}")

                if st.form_submit_button("➕ Adicionar Movimentação", type="primary"):
                    data_hora_entrada_str = datetime.combine(data_entrada_nova, hora_entrada_nova).strftime('%Y-%m-%d %H:%M:%S')
                    if adicionar_tramitacao(dados_tram[0], novo_setor, data_hora_entrada_str, observacao_nova):
                        st.success("✅ Movimentação adicionada com sucesso!")
                        st.rerun()
                    else:
                        st.error("❌ Erro ao adicionar movimentação.")

            st.divider()
            st.subheader("Histórico de Tramitação:")
            tramitacoes = buscar_tramitacoes(dados_tram[0])

            if tramitacoes:
                tempos_setores = calcular_tempo_setores(tramitacoes)

                # Exibir métricas de tempo
                st.markdown("##### ⏱️ Tempo em cada setor:")
                cols_metrics = st.columns(len(tempos_setores) if len(tempos_setores) > 0 else 1)
                for idx, (setor, tempo) in enumerate(tempos_setores.items()):
                    with cols_metrics[idx % len(cols_metrics)]:
                        st.metric(f"{setor}", f"{tempo} dias")

                total_dias = sum(tempos_setores.values())
                st.metric("⏱️ Tempo Total de Tramitação", f"{total_dias} dias")
                st.divider()

                for t in tramitacoes:
                    # t[0]=id, t[1]=processo_id, t[2]=setor, t[3]=data_entrada, t[4]=data_saida, t[5]=observacao
                    data_entrada_fmt = datetime.strptime(t[3], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
                    data_saida_fmt = "Em andamento"
                    if t[4]:
                        data_saida_fmt = datetime.strptime(t[4], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')

                    icon = "➡️"
                    if t[2] == "Protocolo": icon = "📝"
                    elif t[2] == "Requerente": icon = "🧑‍💻"
                    elif t[2] == "Analista": icon = "👩‍🔬"
                    elif t[2] == "Fiscalização": icon = "👮"
                    elif t[2] == "Parecer Externo": icon = "🏢"
                    elif t[2] == "Emissão de Alvará": icon = "📜"
                    elif t[2] == "Arquivo": icon = "🗄️"

                    st.markdown(f"**{icon} {t[2]}**")
                    st.write(f"  - **Entrada:** {data_entrada_fmt}")
                    st.write(f"  - **Saída:** {data_saida_fmt}")
                    if t[5]:
                        st.write(f"  - **Obs:** {t[5]}")

                    col_edit_tram, col_del_tram = st.columns(2)
                    with col_edit_tram:
                        if st.button("✏️ Editar Movimentação", key=f"edit_tram_{t[0]}", use_container_width=True):
                            st.session_state[f"edit_tram_form_{t[0]}"] = True
                    with col_del_tram:
                        if st.button("🗑️ Deletar Movimentação", key=f"del_tram_{t[0]}", use_container_width=True, type="secondary"):
                            if deletar_tramitacao(t[0]):
                                st.success("✅ Movimentação deletada!")
                                st.rerun()
                            else:
                                st.error("❌ Erro ao deletar movimentação.")

                    # Formulário de Edição de Tramitação
                    if st.session_state.get(f"edit_tram_form_{t[0]}", False):
                        st.subheader(f"Editar Movimentação no Setor: {t[2]}")
                        with st.form(f"form_edit_tram_{t[0]}"):
                            ed_setor = st.selectbox("Setor:", setores_disponiveis, 
                                                    index=setores_disponiveis.index(t[2]), 
                                                    key=f"ed_setor_{t[0]}")

                            ed_data_entrada_date = datetime.strptime(t[3], '%Y-%m-%d %H:%M:%S').date()
                            ed_data_entrada_time = datetime.strptime(t[3], '%Y-%m-%d %H:%M:%S').time()
                            ed_data_entrada = st.date_input("Data de Entrada:", value=ed_data_entrada_date, key=f"ed_data_entrada_date_{t[0]}")
                            ed_hora_entrada = st.time_input("Hora de Entrada:", value=ed_data_entrada_time, key=f"ed_hora_entrada_time_{t[0]}")

                            ed_data_saida_date = None
                            ed_data_saida_time = None
                            if t[4]:
                                ed_data_saida_date = datetime.strptime(t[4], '%Y-%m-%d %H:%M:%S').date()
                                ed_data_saida_time = datetime.strptime(t[4], '%Y-%m-%d %H:%M:%S').time()

                            ed_data_saida = st.date_input("Data de Saída (opcional):", value=ed_data_saida_date, key=f"ed_data_saida_date_{t[0]}")
                            ed_hora_saida = st.time_input("Hora de Saída (opcional):", value=ed_data_saida_time, key=f"ed_hora_saida_time_{t[0]}")

                            ed_observacao = st.text_area("Observação:", value=t[5], key=f"ed_obs_{t[0]}")

                            col_tram_btn1, col_tram_btn2 = st.columns(2)
                            with col_tram_btn1:
                                if st.form_submit_button("💾 Salvar Edição", type="primary", key=f"save_edit_tram_{t[0]}"):
                                    data_entrada_full_str = datetime.combine(ed_data_entrada, ed_hora_entrada).strftime('%Y-%m-%d %H:%M:%S')
                                    data_saida_full_str = None
                                    if ed_data_saida:
                                        data_saida_full_str = datetime.combine(ed_data_saida, ed_hora_saida).strftime('%Y-%m-%d %H:%M:%S')

                                    if atualizar_tramitacao(t[0], ed_setor, data_entrada_full_str, data_saida_full_str, ed_observacao):
                                        st.success("✅ Movimentação atualizada!")
                                        st.session_state[f"edit_tram_form_{t[0]}"] = False
                                        st.rerun()
                                    else:
                                        st.error("❌ Erro ao atualizar movimentação.")
                            with col_tram_btn2:
                                if st.form_submit_button("↩️ Cancelar", key=f"cancel_edit_tram_{t[0]}"):
                                    st.session_state[f"edit_tram_form_{t[0]}"] = False
                                    st.rerun()
                    st.markdown("---")
            else:
                st.info("📭 Nenhuma movimentação registrada para este processo.")

# ==================== ABA 4: KANBAN ====================
with tab4:
    st.header("📊 Kanban de Processos")

    status_list = ['Protocolado', 'Em Análise', 'Aguardando Correções', 'Aprovado', 'Reprovado']

    # Cores para os cards (opcional, para visualização)
    status_colors = {
        'Protocolado': '#f0f2f6', # Cinza claro
        'Em Análise': '#e0f2f7',  # Azul claro
        'Aguardando Correções': '#fff3cd', # Amarelo claro
        'Aprovado': '#d4edda',    # Verde claro
        'Reprovado': '#f8d7da'    # Vermelho claro
    }

    cols = st.columns(len(status_list))

    for i, status in enumerate(status_list):
        with cols[i]:
            st.subheader(f"{status} ({len(listar_por_status(status))})")
            st.markdown("---")

            procs_by_status = listar_por_status(status)
            if not procs_by_status:
                st.info("Vazio")

            for p in procs_by_status:
                # p[0]=id, p[1]=numero, p[2]=rt, p[3]=requerente, p[4]=analista, p[5]=uso, p[6]=tipologia, p[7]=area, p[8]=data_protocolo, p[9]=status, p[10]=data_cadastro

                # Card do processo
                st.markdown(f"""
                    <div style='
                        border: 1px solid #ddd;
                        border-left: 5px solid {status_colors.get(status, '#ccc')};
                        padding: 10px;
                        border-radius: 5px;
                        margin-bottom: 10px;
                        background-color: {status_colors.get(status, '#f9f9f9')};
                    '>
                        <b>{p[1]}</b><br>
                        👤 {p[3]}<br>
                        📋 {p[6]}<br>
                        📅 {datetime.strptime(p[8], '%Y-%m-%d').strftime('%d/%m/%Y')}
                    </div>
                    """, unsafe_allow_html=True)

                # Botões para mover entre status
                other_statuses = [s for s in status_list if s != status]

                # Divide os botões em colunas para melhor visualização
                num_other_statuses = len(other_statuses)
                if num_other_statuses > 0:
                    cols_btn = st.columns(num_other_statuses)
                    for btn_idx, new_status in enumerate(other_statuses):
                        with cols_btn[btn_idx]:
                            if st.button(f"→ {new_status}", key=f"move_{p[0]}_{new_status}", 
                                       use_container_width=True, help=f"Mover para {new_status}"):
                                if atualizar_status(p[0], new_status):
                                    st.success(f"✅ Processo {p[1]} movido para '{new_status}'")
                                    st.rerun()
                                else:
                                    st.error(f"❌ Erro ao mover processo {p[1]}.")

                st.markdown("---") # Separador entre cards

# ==================== ABA 5: ANALISAR ====================
with tab5:
    st.header("🤖 Análise Inteligente com IA")

    if not st.session_state.get('api_key'): # Verifica a API Key da sidebar
        st.warning("⚠️ Configure sua API Key do Google Gemini na barra lateral para usar esta função.")
        st.info("**Como obter:** Acesse https://aistudio.google.com/app/apikey e crie uma chave gratuita.")
        st.stop()

    procs = listar()

    if not procs:
        st.info("📭 Cadastre um processo primeiro na aba 'Cadastrar'.")
        st.stop()

    proc_sel = st.selectbox("Selecione o Processo para Análise:", 
                           [f"{p[1]} - {p[3]}" for p in procs], 
                           key="anal_sel")

    if proc_sel:
        num_proc = proc_sel.split(" - ")[0]
        dados = buscar_por_numero(num_proc)

        if dados:
            # p[0]=id, p[1]=numero, p[2]=rt, p[3]=requerente, p[4]=analista, p[5]=uso, p[6]=tipologia, p[7]=area, p[8]=data_protocolo, p[9]=status, p[10]=data_cadastro

            with st.expander("📋 Dados do Processo Selecionado", expanded=True):
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Número", dados[1])
                col2.metric("Uso", dados[5])
                col3.metric("Área", f"{dados[7]}m²")
                col4.metric("Protocolo", datetime.strptime(dados[8], '%Y-%m-%d').strftime('%d/%m/%Y'))

                st.write(f"**RT:** {dados[2]}")
                st.write(f"**Requerente:** {dados[3]}")
                st.write(f"**Analista:** {dados[4]}")
                st.write(f"**Tipologia:** {dados[6]}")
                st.write(f"**Status Atual:** **{dados[9]}**")

            st.divider()

            # Upload de arquivos
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("📐 PDFs do Projeto Arquitetônico")
                proj = st.file_uploader(
                    "Anexe os PDFs do projeto (plantas, cortes, fachadas)", 
                    type=['pdf'], 
                    accept_multiple_files=True, 
                    key="proj_analise"
                )
                if proj:
                    st.success(f"✅ {len(proj)} arquivo(s) anexado(s)")

            with col2:
                st.subheader("📜 PDFs da Legislação Municipal")
                leg = st.file_uploader(
                    "Anexe os PDFs da legislação aplicável", 
                    type=['pdf'], 
                    accept_multiple_files=True, 
                    key="leg_analise"
                )
                if leg:
                    st.success(f"✅ {len(leg)} arquivo(s) anexado(s)")

            st.divider()

            st.subheader("📏 Regras da Legislação a Verificar")
            regras = st.text_area(
                "Digite as regras específicas que devem ser verificadas (uma por linha):", 
                height=150, 
                placeholder="Exemplo:\nArt. 10 - Área mínima de lote: 50m²\nArt. 15 - Recuo frontal mínimo: 5m\nArt. 20 - Taxa de ocupação máxima: 60%",
                key="regras_analise"
            )

            st.divider()

            if st.button("🔍 ANALISAR PROJETO COM INTELIGÊNCIA ARTIFICIAL", type="primary", use_container_width=True):
                if not proj:
                    st.error("❌ Anexe pelo menos 1 PDF do projeto!")
                elif not leg:
                    st.error("❌ Anexe pelo menos 1 PDF da legislação!")
                elif not regras:
                    st.error("❌ Digite as regras que devem ser verificadas!")
                else:
                    with st.spinner("🤖 Analisando projeto com Inteligência Artificial... Aguarde..."):
                        try:
                            # Configurar API
                            genai.configure(api_key=st.session_state.get('api_key')) # Usa a API Key da sidebar

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

                            # Tentar criar modelo
                            model = None
                            for nome in ['gemini-1.5-flash', 'gemini-pro', 'gemini-1.5-pro']:
                                try:
                                    model = genai.GenerativeModel(nome)
                                    st.info(f"✅ Usando modelo: {nome}")
                                    break
                                except:
                                    continue

                            if not model:
                                st.error("❌ Nenhum modelo do Gemini disponível. Verifique sua API Key.")
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
                            st.info("Verifique se sua API Key está correta e se os PDFs são válidos.")

# ==================== ABA 6: DASHBOARD & RELATÓRIOS ====================
with tab6:
    st.header("📈 Dashboard & Relatórios")

    df_processos = get_processos_df()
    df_tramitacoes = get_tramitacoes_df()

    if df_processos.empty:
        st.info("📭 Nenhum processo cadastrado para gerar relatórios.")
    else:
        st.subheader("Visão Geral dos Processos")
        col_total, col_aprovados, col_reprovados, col_analise = st.columns(4)

        total_processos = len(df_processos)
        aprovados = df_processos[df_processos['status'] == 'Aprovado'].shape[0]
        reprovados = df_processos[df_processos['status'] == 'Reprovado'].shape[0]
        em_analise = df_processos[df_processos['status'] == 'Em Análise'].shape[0]

        col_total.metric("Total de Processos", total_processos)
        col_aprovados.metric("Aprovados", aprovados)
        col_reprovados.metric("Reprovados", reprovados)
        col_analise.metric("Em Análise", em_analise)

        st.divider()

        st.subheader("Gráficos de Análise")

        chart_type = st.selectbox(
            "Selecione o tipo de gráfico:",
            ["Status dos Processos (Pizza)", "Uso dos Processos (Barras)", 
             "Tipologia dos Processos (Barras)", "Área dos Projetos (Histograma)",
             "Tempo Médio por Setor (Barras)"],
            key="chart_selector"
        )

        if chart_type == "Status dos Processos (Pizza)":
            fig = px.pie(df_processos, names='status', title='Distribuição de Processos por Status',
                         color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig, use_container_width=True)

        elif chart_type == "Uso dos Processos (Barras)":
            fig = px.bar(df_processos['uso'].value_counts().reset_index(), 
                         x='index', y='uso', 
                         labels={'index': 'Uso', 'uso': 'Número de Processos'},
                         title='Número de Processos por Tipo de Uso',
                         color_discrete_sequence=px.colors.qualitative.Vivid)
            st.plotly_chart(fig, use_container_width=True)

        elif chart_type == "Tipologia dos Processos (Barras)":
            fig = px.bar(df_processos['tipologia'].value_counts().reset_index(), 
                         x='index', y='tipologia', 
                         labels={'index': 'Tipologia', 'tipologia': 'Número de Processos'},
                         title='Número de Processos por Tipologia',
                         color_discrete_sequence=px.colors.qualitative.Bold)
            st.plotly_chart(fig, use_container_width=True)

        elif chart_type == "Área dos Projetos (Histograma)":
            fig = px.histogram(df_processos, x='area', nbins=10, 
                               title='Distribuição da Área dos Projetos (m²)',
                               labels={'area': 'Área (m²)', 'count': 'Número de Projetos'},
                               color_discrete_sequence=px.colors.qualitative.G10)
            st.plotly_chart(fig, use_container_width=True)

        elif chart_type == "Tempo Médio por Setor (Barras)":
            if df_tramitacoes.empty:
                st.info("📭 Nenhuma tramitação registrada para calcular o tempo por setor.")
            else:
                # Agrupar tramitações por processo e calcular o tempo em cada setor
                # Isso é um pouco mais complexo, vamos simplificar para o tempo total por setor

                # Para calcular o tempo médio por setor, precisamos do processo_id
                # e garantir que data_saida - data_entrada seja positivo
                df_tramitacoes_valid = df_tramitacoes[df_tramitacoes['duracao_dias'] >= 0]

                if not df_tramitacoes_valid.empty:
                    # Calcular o tempo total que cada setor teve processos
                    tempo_total_por_setor = df_tramitacoes_valid.groupby('setor')['duracao_dias'].sum().reset_index()

                    fig = px.bar(tempo_total_por_setor, x='setor', y='duracao_dias',
                                 labels={'setor': 'Setor', 'duracao_dias': 'Tempo Total em Dias'},
                                 title='Tempo Total de Processos em Cada Setor',
                                 color_discrete_sequence=px.colors.qualitative.Set2)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Não há dados de tramitação válidos com duração calculada.")


# Rodapé
st.divider()
st.markdown("---")
st.markdown("""
<div style='text-align: center'>
    <p><strong>🏛️ Sistema de Validação de Processos com Inteligência Artificial</strong></p>
    <p>Prefeitura de Contagem - MG • Setor de Liberação de Alvarás de Construção</p>
    <p style='font-size: 0.85em; color: #666;'>Powered by Google Gemini</p>
</div>
""", unsafe_allow_html=True)

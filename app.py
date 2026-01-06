import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime, timedelta
import sqlite3
import os

st.set_page_config(page_title="Sistema de Validação", page_icon="🏛️", layout="wide")

# ==================== BANCO DE DADOS ====================

def reset_database():
    """Reseta o banco de dados, removendo o arquivo e limpando o cache."""
    try:
        if os.path.exists('processos.db'):
            os.remove('processos.db')
        st.cache_resource.clear() # Limpa o cache para forçar a recriação da conexão
        st.success("✅ Banco de dados resetado com sucesso!")
        return init_db()
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
        return False, "❌ Processo com este número já existe!"
    except Exception as e:
        return False, f"❌ Erro ao cadastrar: {str(e)}"

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
        return False, f"❌ Erro ao atualizar: {str(e)}"

def atualizar_status(pid, novo_status):
    """Atualiza o status de um processo."""
    if not conn: return False
    try:
        c = conn.cursor()
        c.execute('UPDATE processos SET status = ? WHERE id = ?', (novo_status, pid))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ Erro ao atualizar status: {str(e)}")
        return False

def listar():
    """Lista todos os processos ordenados pelo ID mais recente."""
    if not conn: return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM processos ORDER BY id DESC')
        return c.fetchall()
    except Exception as e:
        st.error(f"❌ Erro ao listar processos: {str(e)}")
        return []

def listar_por_status(status):
    """Lista processos filtrados por status."""
    if not conn: return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM processos WHERE status = ? ORDER BY id DESC', (status,))
        return c.fetchall()
    except Exception as e:
        st.error(f"❌ Erro ao listar por status: {str(e)}")
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
        st.error(f"❌ Erro ao deletar processo: {str(e)}")
        return False

def salvar_analise(pid, resultado, status):
    """Salva o resultado de uma análise de IA."""
    if not conn: return False
    try:
        c = conn.cursor()
        c.execute('INSERT INTO analises (processo_id, resultado, status) VALUES (?, ?, ?)', 
                 (pid, resultado, status))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ Erro ao salvar análise: {str(e)}")
        return False

def buscar_analises(pid):
    """Busca as análises de um processo."""
    if not conn: return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM analises WHERE processo_id = ? ORDER BY id DESC', (pid,))
        return c.fetchall()
    except Exception as e:
        st.error(f"❌ Erro ao buscar análises: {str(e)}")
        return []

def adicionar_tramitacao(processo_id, setor, data_entrada, observacao=""):
    """Adiciona uma nova movimentação de tramitação."""
    if not conn: return False
    try:
        c = conn.cursor()
        # Fecha a tramitação anterior (se houver alguma em aberto)
        c.execute('''UPDATE tramitacao 
                    SET data_saida = ? 
                    WHERE processo_id = ? AND data_saida IS NULL''', 
                 (data_entrada, processo_id))

        # Adiciona a nova tramitação
        c.execute('''INSERT INTO tramitacao (processo_id, setor, data_entrada, observacao) 
                    VALUES (?, ?, ?, ?)''', 
                 (processo_id, setor, data_entrada, observacao))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ Erro ao registrar tramitação: {str(e)}")
        return False

def atualizar_tramitacao(tram_id, setor, data_entrada, data_saida, observacao):
    """Atualiza uma movimentação de tramitação existente."""
    if not conn: return False
    try:
        c = conn.cursor()
        c.execute('''UPDATE tramitacao 
                    SET setor=?, data_entrada=?, data_saida=?, observacao=?
                    WHERE id=?''',
                 (setor, data_entrada, data_saida, observacao, tram_id))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ Erro ao atualizar tramitação: {str(e)}")
        return False

def deletar_tramitacao(tram_id):
    """Deleta uma movimentação de tramitação."""
    if not conn: return False
    try:
        c = conn.cursor()
        c.execute('DELETE FROM tramitacao WHERE id = ?', (tram_id,))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ Erro ao deletar tramitação: {str(e)}")
        return False

def buscar_tramitacoes(processo_id):
    """Busca o histórico de tramitações de um processo."""
    if not conn: return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM tramitacao WHERE processo_id = ? ORDER BY data_entrada DESC', 
                 (processo_id,))
        return c.fetchall()
    except Exception as e:
        st.error(f"❌ Erro ao buscar tramitações: {str(e)}")
        return []

def calcular_dias(data_entrada_str, data_saida_str):
    """Calcula a diferença em dias entre duas datas (ou até hoje se data_saida_str for None)."""
    try:
        entrada = datetime.strptime(data_entrada_str, "%Y-%m-%d")
        saida = datetime.strptime(data_saida_str, "%Y-%m-%d") if data_saida_str else datetime.now()
        return (saida - entrada).days
    except Exception as e:
        # st.warning(f"Erro ao calcular dias: {e} para entrada={data_entrada_str}, saida={data_saida_str}")
        return 0 # Retorna 0 ou outro valor padrão em caso de erro

def estatisticas_tramitacao(processo_id):
    """Calcula o tempo total em dias que o processo ficou em cada setor."""
    trams = buscar_tramitacoes(processo_id)
    stats = {}
    for t in trams:
        setor = t[2]
        dias = calcular_dias(t[3], t[4])
        if setor in stats:
            stats[setor] += dias
        else:
            stats[setor] = dias
    return stats

# ==================== SIDEBAR ====================
with st.sidebar:
    st.title("⚙️ Configurações")

    api_key = st.text_input("🔑 API Key Gemini:", type="password", help="Obtenha sua chave em: https://aistudio.google.com/app/apikey")

    st.divider()

    # Botão de reset do banco de dados
    if st.button("🔄 Resetar Banco de Dados", type="secondary", help="ATENÇÃO: Isso apagará TODOS os dados existentes e recriará as tabelas com a estrutura mais recente."):
        reset_database()
        st.rerun()

    st.divider()

    # Métricas gerais
    procs_geral = listar()
    st.metric("📊 Total de Processos", len(procs_geral))

    if procs_geral:
        usos = {}
        for p in procs_geral:
            uso = p[5]
            usos[uso] = usos.get(uso, 0) + 1

        st.divider()
        st.subheader("📈 Processos por Uso")
        for uso, qtd in usos.items():
            st.metric(uso, qtd)

# ==================== ABAS PRINCIPAIS ====================
tab1, tab2, tab3, tab4, tab5 = st.tabs(["➕ Cadastrar", "📋 Gerenciar", "🔄 Tramitação", "📊 Kanban", "🤖 Analisar"])

# ==================== ABA 1: CADASTRAR ====================
with tab1:
    st.header("➕ Cadastrar Novo Processo")

    with st.form("form_cadastro", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            numero = st.text_input("📄 Número do Processo *", placeholder="Ex: 2024.001.123")
            rt = st.text_input("👷 Responsável Técnico *", placeholder="Nome do RT")
            requerente = st.text_input("🏢 Requerente *", placeholder="Nome do requerente")
            analista = st.text_input("👤 Analista *", placeholder="Nome do analista")

        with col2:
            uso = st.selectbox("🏗️ Uso *", [
                "", # Opção vazia para forçar seleção
                "Unifamiliar",
                "Multifamiliar",
                "Serviços",
                "Comércio Varejista",
                "Comércio Atacadista",
                "Indústria",
                "Misto",
                "Sem destinação específica"
            ])

            tipologia = st.selectbox("📐 Tipologia *", [
                "", # Opção vazia para forçar seleção
                "Aprovação Inicial",
                "Levantamento Existente",
                "Modificação de Projeto",
                "Regularização",
                "Misto",
                "RIU",
                "ERB",
                "As Built"
            ])

            area = st.number_input("📏 Área Construída (m²) *", min_value=0.0, step=0.01, format="%.2f")
            data_protocolo = st.date_input("📅 Data do Protocolo *", value=datetime.now().date())

        st.markdown("*Campos obrigatórios")

        submitted = st.form_submit_button("💾 CADASTRAR PROCESSO", type="primary", use_container_width=True)

        if submitted:
            if not all([numero, rt, requerente, analista, uso, tipologia, area > 0, data_protocolo]):
                st.error("❌ Por favor, preencha todos os campos obrigatórios!")
            else:
                sucesso, msg = cadastrar(numero, rt, requerente, analista, uso, tipologia, area, 
                                        data_protocolo.strftime('%Y-%m-%d'))
                if sucesso:
                    st.success(msg)
                    st.balloons()
                else:
                    st.error(msg)

# ==================== ABA 2: GERENCIAR ====================
with tab2:
    st.header("📋 Gerenciar Processos")

    procs = listar()

    if not procs:
        st.info("📭 Nenhum processo cadastrado ainda. Use a aba 'Cadastrar' para adicionar.")
    else:
        st.write(f"**Mostrando {len(procs)} processo(s)**")
        st.divider()

        for p in procs:
            # p[0]=id, p[1]=numero, p[2]=rt, p[3]=requerente, p[4]=analista, p[5]=uso, p[6]=tipologia, p[7]=area, p[8]=data_protocolo, p[9]=status, p[10]=data_cadastro

            with st.expander(f"📄 Processo {p[1]} - {p[3]} | Status: {p[9]}", expanded=False):

                # Inicializa o estado de edição para cada processo
                if f"edit_proc_{p[0]}" not in st.session_state:
                    st.session_state[f"edit_proc_{p[0]}"] = False

                # Se não estiver em modo de edição, mostra a visualização normal
                if not st.session_state[f"edit_proc_{p[0]}"]:
                    col_info, col_btns = st.columns([4, 1])

                    with col_info:
                        st.markdown(f"**Número:** {p[1]}")
                        st.markdown(f"**RT:** {p[2]}")
                        st.markdown(f"**Requerente:** {p[3]}")
                        st.markdown(f"**Analista:** {p[4]}")
                        st.markdown(f"**Uso:** {p[5]} | **Tipologia:** {p[6]}")
                        st.markdown(f"**Área:** {p[7]}m²")
                        st.markdown(f"**Data Protocolo:** {datetime.strptime(p[8], '%Y-%m-%d').strftime('%d/%m/%Y')}")
                        st.markdown(f"**Status Atual:** **{p[9]}**")
                        st.markdown(f"**Cadastrado em:** {datetime.strptime(p[10], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')}")

                        # Análises
                        analises = buscar_analises(p[0])
                        if analises:
                            st.divider()
                            st.markdown("**📊 Histórico de Análises:**")
                            for a in analises:
                                icone = "✅" if a[3] == "APROVADO" else "❌" if a[3] == "REPROVADO" else "⚠️"
                                with st.expander(f"{icone} {a[4]} - **{a[3]}**", expanded=False):
                                    st.markdown(a[2])

                    with col_btns:
                        if st.button("✏️", key=f"btn_edit_proc_{p[0]}", help="Editar processo"):
                            st.session_state[f"edit_proc_{p[0]}"] = True
                            st.rerun()

                        if st.button("🗑️", key=f"btn_del_proc_{p[0]}", help="Deletar processo"):
                            if deletar(p[0]):
                                st.success("✅ Processo deletado!")
                                st.rerun()
                            else:
                                st.error("❌ Erro ao deletar")

                # Se estiver em modo de edição, mostra o formulário de edição
                else:
                    st.subheader("✏️ Editar Processo")

                    with st.form(f"form_edit_proc_{p[0]}"):
                        col1, col2 = st.columns(2)

                        with col1:
                            ed_numero = st.text_input("Número", value=p[1], key=f"ed_num_{p[0]}")
                            ed_rt = st.text_input("RT", value=p[2], key=f"ed_rt_{p[0]}")
                            ed_req = st.text_input("Requerente", value=p[3], key=f"ed_req_{p[0]}")
                            ed_ana = st.text_input("Analista", value=p[4], key=f"ed_ana_{p[0]}")

                        with col2:
                            ed_uso = st.selectbox("Uso", [
                                "Unifamiliar", "Multifamiliar", "Serviços",
                                "Comércio Varejista", "Comércio Atacadista",
                                "Indústria", "Misto", "Sem destinação específica"
                            ], index=["Unifamiliar", "Multifamiliar", "Serviços",
                                     "Comércio Varejista", "Comércio Atacadista",
                                     "Indústria", "Misto", "Sem destinação específica"].index(p[5]), 
                            key=f"ed_uso_{p[0]}")

                            ed_tip = st.selectbox("Tipologia", [
                                "Aprovação Inicial", "Levantamento Existente",
                                "Modificação de Projeto", "Regularização",
                                "Misto", "RIU", "ERB", "As Built"
                            ], index=["Aprovação Inicial", "Levantamento Existente",
                                     "Modificação de Projeto", "Regularização",
                                     "Misto", "RIU", "ERB", "As Built"].index(p[6]),
                            key=f"ed_tip_{p[0]}")

                            ed_area = st.number_input("Área", value=float(p[7]), step=0.01, key=f"ed_area_{p[0]}")
                            ed_data_protocolo = st.date_input("Data Protocolo", 
                                                   value=datetime.strptime(p[8], '%Y-%m-%d').date(),
                                                   key=f"ed_data_prot_{p[0]}")

                        col_save, col_cancel = st.columns(2)

                        with col_save:
                            if st.form_submit_button("💾 Salvar Alterações", type="primary", use_container_width=True):
                                sucesso, msg = atualizar(p[0], ed_numero, ed_rt, ed_req, ed_ana, 
                                                        ed_uso, ed_tip, ed_area, ed_data_protocolo.strftime('%Y-%m-%d'))
                                if sucesso:
                                    st.success(msg)
                                    st.session_state[f"edit_proc_{p[0]}"] = False
                                    st.rerun()
                                else:
                                    st.error(msg)

                        with col_cancel:
                            if st.form_submit_button("❌ Cancelar Edição", use_container_width=True):
                                st.session_state[f"edit_proc_{p[0]}"] = False
                                st.rerun()

# ==================== ABA 3: TRAMITAÇÃO ====================
with tab3:
    st.header("🔄 Gestão de Tramitação")

    procs = listar()

    if not procs:
        st.info("📭 Cadastre um processo primeiro na aba 'Cadastrar'")
    else:
        # Seleção do processo
        proc_sel = st.selectbox("Selecione o Processo:", 
                               [f"{p[1]} - {p[3]}" for p in procs], 
                               key="tram_sel")

        if proc_sel:
            num_proc = proc_sel.split(" - ")[0]
            processo = buscar_por_numero(num_proc)

            if processo:
                st.divider()

                # Adicionar nova movimentação
                st.subheader("➕ Registrar Nova Movimentação")

                with st.form("form_tramitacao", clear_on_submit=True):
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        setor_opcoes = [
                            "Requerente",
                            "Analista",
                            "Fiscalização",
                            "Parecer Externo",
                            "Emissão de Alvará",
                            "Protocolo",
                            "Arquivo"
                        ]
                        setor = st.selectbox("Setor Responsável:", setor_opcoes, key="tram_setor")

                    with col2:
                        data_mov = st.date_input("Data da Movimentação:", value=datetime.now().date(), key="tram_data")

                    with col3:
                        obs = st.text_input("Observação:", key="tram_obs", placeholder="Ex: Retornou para correções")

                    if st.form_submit_button("✅ Registrar Movimentação", type="primary", use_container_width=True):
                        if adicionar_tramitacao(processo[0], setor, data_mov.strftime('%Y-%m-%d'), obs):
                            st.success("✅ Movimentação registrada com sucesso!")
                            st.rerun()
                        else:
                            st.error("❌ Erro ao registrar movimentação")

                st.divider()

                # Histórico
                st.subheader("📊 Histórico de Tramitação")

                tramitacoes = buscar_tramitacoes(processo[0])

                if tramitacoes:
                    # Estatísticas
                    stats = estatisticas_tramitacao(processo[0])

                    if stats:
                        st.markdown("### 📈 Tempo por Setor")

                        # Garante que sempre haverá colunas para exibir, mesmo que o número de setores seja pequeno
                        num_cols = max(1, len(stats)) 
                        cols = st.columns(num_cols)

                        for idx, (setor, dias) in enumerate(stats.items()):
                            with cols[idx % num_cols]: # Usa módulo para distribuir em colunas se houver mais setores que colunas
                                st.metric(setor, f"{dias} dias")

                        total_dias = sum(stats.values())
                        st.divider()
                        st.metric("⏱️ **Tempo Total de Tramitação**", f"{total_dias} dias")
                        st.divider()

                    # Detalhamento das movimentações
                    st.markdown("### 📋 Detalhamento das Movimentações")

                    for t in tramitacoes:
                        # t[0]=id, t[1]=processo_id, t[2]=setor, t[3]=data_entrada, t[4]=data_saida, t[5]=observacao

                        # Inicializa o estado de edição para cada tramitação
                        if f"edit_tram_{t[0]}" not in st.session_state:
                            st.session_state[f"edit_tram_{t[0]}"] = False

                        # Se não estiver em modo de edição, mostra a visualização normal
                        if not st.session_state[f"edit_tram_{t[0]}"]:
                            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1, 1])

                            with col1:
                                icones_setor = {
                                    "Requerente": "👤", "Analista": "👨‍💼", "Fiscalização": "🔍",
                                    "Parecer Externo": "📋", "Emissão de Alvará": "✅",
                                    "Protocolo": "📥", "Arquivo": "📁"
                                }
                                icone = icones_setor.get(t[2], "📌")
                                st.write(f"{icone} **{t[2]}**")

                            with col2:
                                entrada = datetime.strptime(t[3], '%Y-%m-%d').strftime('%d/%m/%Y')
                                st.write(f"📥 {entrada}")

                            with col3:
                                if t[4]:
                                    saida = datetime.strptime(t[4], '%Y-%m-%d').strftime('%d/%m/%Y')
                                    st.write(f"📤 {saida}")
                                else:
                                    st.write("🔄 **Em andamento**")

                            with col4:
                                tempo = calcular_dias(t[3], t[4])
                                st.metric("Dias", tempo)

                            with col5:
                                if st.button("✏️", key=f"btn_edit_tram_item_{t[0]}", help="Editar movimentação"):
                                    st.session_state[f"edit_tram_{t[0]}"] = True
                                    st.rerun()

                                if st.button("🗑️", key=f"btn_del_tram_item_{t[0]}", help="Deletar movimentação"):
                                    if deletar_tramitacao(t[0]):
                                        st.success("✅ Movimentação deletada!")
                                        st.rerun()

                            if t[5]:
                                st.caption(f"💬 {t[5]}")

                        # Se estiver em modo de edição, mostra o formulário de edição
                        else:
                            st.subheader(f"✏️ Editando Movimentação #{t[0]}")
                            with st.form(f"form_edit_tram_item_{t[0]}"):
                                col_ed1, col_ed2 = st.columns(2)

                                with col_ed1:
                                    ed_setor = st.selectbox("Setor", setor_opcoes, 
                                                            index=setor_opcoes.index(t[2]),
                                                            key=f"ed_setor_tram_{t[0]}")
                                    ed_entrada = st.date_input("Data Entrada", 
                                                               value=datetime.strptime(t[3], '%Y-%m-%d').date(),
                                                               key=f"ed_entrada_tram_{t[0]}")

                                with col_ed2:
                                    ed_saida = st.date_input("Data Saída", 
                                                             value=datetime.strptime(t[4], '%Y-%m-%d').date() if t[4] else None,
                                                             key=f"ed_saida_tram_{t[0]}")
                                    ed_obs = st.text_area("Observação", value=t[5] or "", key=f"ed_obs_tram_{t[0]}")

                                col_save, col_cancel = st.columns(2)

                                with col_save:
                                    if st.form_submit_button("💾 Salvar Alterações", type="primary", use_container_width=True):
                                        if atualizar_tramitacao(t[0], ed_setor, 
                                                               ed_entrada.strftime('%Y-%m-%d'),
                                                               ed_saida.strftime('%Y-%m-%d') if ed_saida else None,
                                                               ed_obs):
                                            st.success("✅ Movimentação atualizada!")
                                            st.session_state[f"edit_tram_{t[0]}"] = False
                                            st.rerun()

                                with col_cancel:
                                    if st.form_submit_button("❌ Cancelar Edição", use_container_width=True):
                                        st.session_state[f"edit_tram_{t[0]}"] = False
                                        st.rerun()

                        st.divider() # Separador para cada item do histórico
                else:
                    st.info("📭 Nenhuma movimentação registrada para este processo")

# ==================== ABA 4: KANBAN ====================
with tab4:
    st.header("📊 Kanban - Gestão Visual de Processos")

    status_list = ["Protocolado", "Em Análise", "Aguardando Correções", "Aprovado", "Reprovado"]

    cols = st.columns(len(status_list))

    for idx, status in enumerate(status_list):
        with cols[idx]:
            # Cor do card por status
            if status == "Aprovado":
                color = "green"
            elif status == "Reprovado":
                color = "red"
            elif status == "Em Análise":
                color = "blue"
            elif status == "Aguardando Correções":
                color = "orange"
            else: # Protocolado
                color = "gray"

            procs_status = listar_por_status(status)

            st.markdown(f"### :{color}[{status}]")
            st.caption(f"Total: {len(procs_status)} processo(s)")

            st.divider()

            if not procs_status:
                st.info("Nenhum processo aqui.")
            else:
                for p in procs_status:
                    # p[0]=id, p[1]=numero, p[2]=rt, p[3]=requerente, p[4]=analista, p[5]=uso, p[6]=tipologia, p[7]=area, p[8]=data_protocolo, p[9]=status, p[10]=data_cadastro

                    st.markdown(f"""
                    <div style='
                        padding: 15px;
                        border-radius: 10px;
                        border-left: 5px solid {color};
                        background-color: rgba(128,128,128,0.1);
                        margin-bottom: 10px;
                    '>
                        <b>{p[1]}</b><br>
                        👤 {p[3]}<br>
                        📋 {p[6]}<br>
                        📅 {datetime.strptime(p[8], '%Y-%m-%d').strftime('%d/%m/%Y')}
                    </div>
                    """, unsafe_allow_html=True)

                    # Botões para mover entre status
                    # Cria uma lista de status para os botões, excluindo o status atual
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

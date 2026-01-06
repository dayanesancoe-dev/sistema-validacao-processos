import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime, timedelta
import sqlite3
import os

st.set_page_config(page_title="Sistema de Validação", page_icon="🏛️", layout="wide")

# ==================== BANCO DE DADOS ====================

def reset_database():
    """Reseta o banco"""
    try:
        if os.path.exists('processos.db'):
            os.remove('processos.db')
        st.cache_resource.clear()
        return init_db()
    except Exception as e:
        st.error(f"Erro ao resetar: {str(e)}")
        return None

@st.cache_resource
def init_db():
    """Inicializa banco"""
    try:
        conn = sqlite3.connect('processos.db', check_same_thread=False)
        c = conn.cursor()

        # Verificar estrutura antiga
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processos'")
        if c.fetchone():
            c.execute("PRAGMA table_info(processos)")
            colunas = [col[1] for col in c.fetchall()]
            if 'data_protocolo' not in colunas:
                c.execute('DROP TABLE IF EXISTS tramitacao')
                c.execute('DROP TABLE IF EXISTS analises')
                c.execute('DROP TABLE IF EXISTS processos')

        # Criar tabelas
        c.execute('''CREATE TABLE IF NOT EXISTS processos (
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
        st.error(f"Erro: {str(e)}")
        return None

conn = init_db()

# ==================== FUNÇÕES ====================

def cadastrar(numero, rt, requerente, analista, uso, tipologia, area, data_protocolo):
    if not conn:
        return False, "❌ Erro!"
    try:
        c = conn.cursor()
        c.execute('''INSERT INTO processos 
                    (numero, rt, requerente, analista, uso, tipologia, area, data_protocolo) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                 (numero, rt, requerente, analista, uso, tipologia, area, data_protocolo))
        conn.commit()
        return True, "✅ Cadastrado!"
    except sqlite3.IntegrityError:
        return False, "❌ Processo já existe!"
    except Exception as e:
        return False, f"❌ Erro: {str(e)}"

def atualizar(pid, numero, rt, requerente, analista, uso, tipologia, area, data_protocolo):
    if not conn:
        return False, "❌ Erro!"
    try:
        c = conn.cursor()
        c.execute('''UPDATE processos 
                    SET numero=?, rt=?, requerente=?, analista=?, uso=?, tipologia=?, area=?, data_protocolo=?
                    WHERE id=?''',
                 (numero, rt, requerente, analista, uso, tipologia, area, data_protocolo, pid))
        conn.commit()
        return True, "✅ Atualizado!"
    except Exception as e:
        return False, f"❌ Erro: {str(e)}"

def atualizar_status(pid, novo_status):
    if not conn:
        return False
    try:
        c = conn.cursor()
        c.execute('UPDATE processos SET status = ? WHERE id = ?', (novo_status, pid))
        conn.commit()
        return True
    except:
        return False

def listar():
    if not conn:
        return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM processos ORDER BY id DESC')
        return c.fetchall()
    except:
        return []

def listar_por_status(status):
    if not conn:
        return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM processos WHERE status = ? ORDER BY id DESC', (status,))
        return c.fetchall()
    except:
        return []

def buscar_por_numero(numero):
    if not conn:
        return None
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM processos WHERE numero = ?', (numero,))
        return c.fetchone()
    except:
        return None

def deletar(pid):
    if not conn:
        return False
    try:
        c = conn.cursor()
        c.execute('DELETE FROM analises WHERE processo_id = ?', (pid,))
        c.execute('DELETE FROM tramitacao WHERE processo_id = ?', (pid,))
        c.execute('DELETE FROM processos WHERE id = ?', (pid,))
        conn.commit()
        return True
    except:
        return False

def salvar_analise(pid, resultado, status):
    if not conn:
        return False
    try:
        c = conn.cursor()
        c.execute('INSERT INTO analises (processo_id, resultado, status) VALUES (?, ?, ?)', 
                 (pid, resultado, status))
        conn.commit()
        return True
    except:
        return False

def buscar_analises(pid):
    if not conn:
        return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM analises WHERE processo_id = ? ORDER BY id DESC', (pid,))
        return c.fetchall()
    except:
        return []

def adicionar_tramitacao(processo_id, setor, data_entrada, observacao=""):
    if not conn:
        return False
    try:
        c = conn.cursor()
        c.execute('''UPDATE tramitacao 
                    SET data_saida = ? 
                    WHERE processo_id = ? AND data_saida IS NULL''', 
                 (data_entrada, processo_id))

        c.execute('''INSERT INTO tramitacao (processo_id, setor, data_entrada, observacao) 
                    VALUES (?, ?, ?, ?)''', 
                 (processo_id, setor, data_entrada, observacao))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro: {str(e)}")
        return False

def listar_tramitacao(processo_id):
    if not conn:
        return []
    try:
        c = conn.cursor()
        c.execute('''SELECT * FROM tramitacao 
                    WHERE processo_id = ? 
                    ORDER BY data_entrada DESC''', (processo_id,))
        return c.fetchall()
    except:
        return []

def atualizar_tramitacao(tram_id, setor, data_entrada, data_saida, observacao):
    if not conn:
        return False
    try:
        c = conn.cursor()
        c.execute('''UPDATE tramitacao 
                    SET setor=?, data_entrada=?, data_saida=?, observacao=?
                    WHERE id=?''',
                 (setor, data_entrada, data_saida, observacao, tram_id))
        conn.commit()
        return True
    except:
        return False

def deletar_tramitacao(tram_id):
    if not conn:
        return False
    try:
        c = conn.cursor()
        c.execute('DELETE FROM tramitacao WHERE id = ?', (tram_id,))
        conn.commit()
        return True
    except:
        return False

def calcular_dias(data_entrada, data_saida):
    try:
        entrada = datetime.strptime(data_entrada, "%Y-%m-%d")
        saida = datetime.strptime(data_saida, "%Y-%m-%d") if data_saida else datetime.now()
        return (saida - entrada).days
    except:
        return 0

# ==================== SIDEBAR ====================
with st.sidebar:
    st.title("⚙️ Configurações")

    api_key = st.text_input("🔑 API Key:", type="password", help="Gemini API")

    if st.button("🔄 Resetar Banco", type="secondary"):
        reset_database()
        st.success("✅ Banco resetado!")
        st.rerun()

    st.divider()

    procs = listar()
    st.metric("Total de Processos", len(procs))

    if procs:
        usos = {}
        for p in procs:
            uso = p[5]
            usos[uso] = usos.get(uso, 0) + 1

        st.divider()
        st.subheader("📊 Por Uso")
        for uso, qtd in usos.items():
            st.metric(uso, qtd)

# ==================== ABAS ====================
tab1, tab2, tab3, tab4, tab5 = st.tabs(["➕ Cadastrar", "📋 Gerenciar", "🔄 Tramitação", "📊 Kanban", "🤖 Analisar"])

# ==================== ABA 1: CADASTRAR ====================
with tab1:
    st.header("➕ Cadastrar Processo")

    with st.form("form_cadastro", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            numero = st.text_input("Número do Processo *")
            rt = st.text_input("Responsável Técnico *")
            requerente = st.text_input("Requerente *")
            analista = st.text_input("Analista *")

        with col2:
            uso = st.selectbox("Uso *", [
                "Unifamiliar",
                "Multifamiliar",
                "Serviços",
                "Comércio Varejista",
                "Comércio Atacadista",
                "Indústria",
                "Misto",
                "Sem destinação específica"
            ])

            tipologia = st.selectbox("Tipologia *", [
                "Aprovação Inicial",
                "Levantamento Existente",
                "Modificação de Projeto",
                "Regularização",
                "Misto",
                "RIU",
                "ERB",
                "As Built"
            ])

            area = st.number_input("Área Construída (m²) *", min_value=0.0, step=0.01)
            data_protocolo = st.date_input("Data do Protocolo *")

        submitted = st.form_submit_button("💾 SALVAR", type="primary", use_container_width=True)

        if submitted:
            if not all([numero, rt, requerente, analista, area > 0]):
                st.error("❌ Preencha todos os campos!")
            else:
                sucesso, msg = cadastrar(numero, rt, requerente, analista, uso, tipologia, area, 
                                        data_protocolo.strftime("%Y-%m-%d"))
                if sucesso:
                    st.success(msg)
                    st.balloons()
                else:
                    st.error(msg)

# ==================== ABA 2: GERENCIAR ====================
with tab2:
    st.header("📋 Processos")

    procs = listar()

    if not procs:
        st.info("📭 Nenhum processo")
    else:
        for p in procs:
            with st.expander(f"📄 {p[1]} - {p[3]} | {p[9]}"):

                # Modo de edição
                if f"edit_{p[0]}" not in st.session_state:
                    st.session_state[f"edit_{p[0]}"] = False

                col1, col2 = st.columns([6, 1])

                with col2:
                    if st.button("✏️", key=f"btn_edit_{p[0]}"):
                        st.session_state[f"edit_{p[0]}"] = not st.session_state[f"edit_{p[0]}"]
                        st.rerun()

                if st.session_state[f"edit_{p[0]}"]:
                    # Formulário de edição
                    with st.form(f"form_edit_{p[0]}"):
                        e_numero = st.text_input("Número", p[1])
                        e_rt = st.text_input("RT", p[2])
                        e_requerente = st.text_input("Requerente", p[3])
                        e_analista = st.text_input("Analista", p[4])
                        e_uso = st.selectbox("Uso", [
                            "Unifamiliar", "Multifamiliar", "Serviços",
                            "Comércio Varejista", "Comércio Atacadista",
                            "Indústria", "Misto", "Sem destinação específica"
                        ], index=["Unifamiliar", "Multifamiliar", "Serviços",
                            "Comércio Varejista", "Comércio Atacadista",
                            "Indústria", "Misto", "Sem destinação específica"].index(p[5]))
                        e_tipologia = st.selectbox("Tipologia", [
                            "Aprovação Inicial", "Levantamento Existente",
                            "Modificação de Projeto", "Regularização",
                            "Misto", "RIU", "ERB", "As Built"
                        ], index=["Aprovação Inicial", "Levantamento Existente",
                            "Modificação de Projeto", "Regularização",
                            "Misto", "RIU", "ERB", "As Built"].index(p[6]))
                        e_area = st.number_input("Área", value=float(p[7]), min_value=0.0)
                        e_data_protocolo = st.date_input("Data Protocolo", 
                                                        value=datetime.strptime(p[8], "%Y-%m-%d").date())

                        col_save, col_cancel = st.columns(2)
                        with col_save:
                            save = st.form_submit_button("💾 Salvar", type="primary")
                        with col_cancel:
                            cancel = st.form_submit_button("❌ Cancelar")

                        if save:
                            sucesso, msg = atualizar(p[0], e_numero, e_rt, e_requerente, e_analista,
                                                   e_uso, e_tipologia, e_area, 
                                                   e_data_protocolo.strftime("%Y-%m-%d"))
                            if sucesso:
                                st.success(msg)
                                st.session_state[f"edit_{p[0]}"] = False
                                st.rerun()
                            else:
                                st.error(msg)

                        if cancel:
                            st.session_state[f"edit_{p[0]}"] = False
                            st.rerun()
                else:
                    # Visualização normal
                    st.write(f"**RT:** {p[2]}")
                    st.write(f"**Requerente:** {p[3]}")
                    st.write(f"**Analista:** {p[4]}")
                    st.write(f"**Uso:** {p[5]} | **Tipologia:** {p[6]}")
                    st.write(f"**Área:** {p[7]}m²")
                    st.write(f"**Protocolo:** {datetime.strptime(p[8], '%Y-%m-%d').strftime('%d/%m/%Y')}")
                    st.write(f"**Status:** {p[9]}")
                    st.write(f"**Cadastrado:** {p[10]}")

                    analises = buscar_analises(p[0])
                    if analises:
                        st.divider()
                        st.write("**📊 Análises:**")
                        for a in analises:
                            st.info(f"**{a[3]}** - {a[4]}")

                    st.divider()
                    if st.button("🗑️ Deletar", key=f"del_{p[0]}", type="secondary"):
                        if deletar(p[0]):
                            st.success("✅ Deletado!")
                            st.rerun()

# ==================== ABA 3: TRAMITAÇÃO ====================
with tab3:
    st.header("🔄 Tramitação")

    procs = listar()

    if not procs:
        st.info("📭 Cadastre um processo")
        st.stop()

    proc_sel = st.selectbox("Processo:", [f"{p[1]} - {p[3]}" for p in procs], key="tram_sel")

    if proc_sel:
        num_proc = proc_sel.split(" - ")[0]
        dados = buscar_por_numero(num_proc)

        if dados:
            st.divider()

            with st.form("form_tramitacao"):
                st.subheader("📝 Nova Movimentação")

                col1, col2, col3 = st.columns(3)

                with col1:
                    setor = st.selectbox("Setor:", [
                        "📥 Requerente",
                        "👤 Analista",
                        "🔍 Fiscalização",
                        "📋 Parecer Externo",
                        "✅ Emissão de Alvará",
                        "📂 Protocolo",
                        "🗄️ Arquivo"
                    ])

                with col2:
                    data_entrada = st.date_input("Data Entrada:")

                with col3:
                    obs = st.text_input("Observação:")

                if st.form_submit_button("➕ ADICIONAR", type="primary"):
                    if adicionar_tramitacao(dados[0], setor, data_entrada.strftime("%Y-%m-%d"), obs):
                        st.success("✅ Adicionado!")
                        st.rerun()

            st.divider()
            st.subheader("📜 Histórico")

            trams = listar_tramitacao(dados[0])

            if trams:
                stats = {}

                for t in trams:
                    # Modo de edição
                    if f"edit_tram_{t[0]}" not in st.session_state:
                        st.session_state[f"edit_tram_{t[0]}"] = False

                    dias = calcular_dias(t[3], t[4])
                    stats[t[2]] = stats.get(t[2], 0) + dias

                    with st.expander(f"{t[2]} - {dias} dias"):
                        col1, col2 = st.columns([6, 1])

                        with col2:
                            if st.button("✏️", key=f"btn_edit_tram_{t[0]}"):
                                st.session_state[f"edit_tram_{t[0]}"] = not st.session_state[f"edit_tram_{t[0]}"]
                                st.rerun()

                        if st.session_state[f"edit_tram_{t[0]}"]:
                            with st.form(f"form_edit_tram_{t[0]}"):
                                e_setor = st.selectbox("Setor", [
                                    "📥 Requerente", "👤 Analista", "🔍 Fiscalização",
                                    "📋 Parecer Externo", "✅ Emissão de Alvará",
                                    "📂 Protocolo", "🗄️ Arquivo"
                                ], index=[
                                    "📥 Requerente", "👤 Analista", "🔍 Fiscalização",
                                    "📋 Parecer Externo", "✅ Emissão de Alvará",
                                    "📂 Protocolo", "🗄️ Arquivo"
                                ].index(t[2]))

                                e_entrada = st.date_input("Entrada", 
                                    value=datetime.strptime(t[3], "%Y-%m-%d").date())

                                e_saida = st.date_input("Saída", 
                                    value=datetime.strptime(t[4], "%Y-%m-%d").date() if t[4] else None)

                                e_obs = st.text_input("Observação", value=t[5] or "")

                                col_save, col_cancel, col_del = st.columns(3)

                                with col_save:
                                    save = st.form_submit_button("💾 Salvar")
                                with col_cancel:
                                    cancel = st.form_submit_button("❌ Cancelar")
                                with col_del:
                                    delete = st.form_submit_button("🗑️ Deletar", type="secondary")

                                if save:
                                    if atualizar_tramitacao(
                                        t[0], e_setor, 
                                        e_entrada.strftime("%Y-%m-%d"),
                                        e_saida.strftime("%Y-%m-%d") if e_saida else None,
                                        e_obs
                                    ):
                                        st.success("✅ Atualizado!")
                                        st.session_state[f"edit_tram_{t[0]}"] = False
                                        st.rerun()

                                if cancel:
                                    st.session_state[f"edit_tram_{t[0]}"] = False
                                    st.rerun()

                                if delete:
                                    if deletar_tramitacao(t[0]):
                                        st.success("✅ Deletado!")
                                        st.session_state[f"edit_tram_{t[0]}"] = False
                                        st.rerun()
                        else:
                            st.write(f"**Entrada:** {datetime.strptime(t[3], '%Y-%m-%d').strftime('%d/%m/%Y')}")
                            if t[4]:
                                st.write(f"**Saída:** {datetime.strptime(t[4], '%Y-%m-%d').strftime('%d/%m/%Y')}")
                            else:
                                st.write(f"**Saída:** Em andamento")
                            st.write(f"**Dias:** {dias}")
                            if t[5]:
                                st.write(f"**Obs:** {t[5]}")

                st.divider()
                st.subheader("📊 Estatísticas")

                if stats:
                    cols = st.columns(len(stats))
                    for idx, (setor, dias) in enumerate(stats.items()):
                        cols[idx].metric(setor, f"{dias} dias")

                    total = sum(stats.values())
                    st.divider()
                    st.metric("⏱️ Tempo Total", f"{total} dias")
            else:
                st.info("📭 Nenhuma movimentação")

# ==================== ABA 4: KANBAN ====================
with tab4:
    st.header("📊 Kanban - Gestão Visual")

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
            else:
                color = "gray"

            procs_status = listar_por_status(status)

            st.markdown(f"### :{color}[{status}]")
            st.caption(f"{len(procs_status)} processos")

            st.divider()

            for p in procs_status:
                with st.container():
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
                    cols_btn = st.columns(len(status_list) - 1)
                    btn_idx = 0

                    for new_status in status_list:
                        if new_status != status:
                            with cols_btn[btn_idx]:
                                if st.button(f"→ {new_status}", key=f"move_{p[0]}_{new_status}", 
                                           use_container_width=True):
                                    if atualizar_status(p[0], new_status):
                                        st.success(f"✅ Movido para {new_status}")
                                        st.rerun()
                            btn_idx += 1

                    st.divider()

# ==================== ABA 5: ANALISAR ====================
with tab5:
    st.header("🤖 Analisar")

    if not api_key:
        st.warning("⚠️ Configure API")
        st.stop()

    procs = listar()

    if not procs:
        st.info("📭 Cadastre um processo")
        st.stop()

    proc_sel = st.selectbox("Processo:", [f"{p[1]} - {p[3]}" for p in procs], key="anal_sel")

    if proc_sel:
        num_proc = proc_sel.split(" - ")[0]
        dados = buscar_por_numero(num_proc)

        if dados:
            with st.expander("📋 Dados", expanded=True):
                col1, col2, col3 = st.columns(3)
                col1.metric("Número", dados[1])
                col2.metric("Uso", dados[5])
                col3.metric("Área", f"{dados[7]}m²")

            st.divider()

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("📐 Projeto")
                proj = st.file_uploader("PDFs", type=['pdf'], accept_multiple_files=True, key="proj")

            with col2:
                st.subheader("📜 Legislação")
                leg = st.file_uploader("PDFs", type=['pdf'], accept_multiple_files=True, key="leg")

            st.divider()
            regras = st.text_area("📏 Regras:", height=150, placeholder="Art. 10 - Área mínima 50m²")

            st.divider()

            if st.button("🔍 ANALISAR", type="primary"):
                if not proj or not leg or not regras:
                    st.error("❌ Anexe PDFs e regras!")
                else:
                    with st.spinner("🤖 Analisando..."):
                        try:
                            genai.configure(api_key=api_key)

                            txt_proj = ""
                            for pdf in proj:
                                reader = PyPDF2.PdfReader(pdf)
                                for page in reader.pages:
                                    txt_proj += page.extract_text() + "\n"

                            txt_leg = ""
                            for pdf in leg:
                                reader = PyPDF2.PdfReader(pdf)
                                for page in reader.pages:
                                    txt_leg += page.extract_text() + "\n"

                            model = None
                            for nome in ['gemini-1.5-flash', 'gemini-pro']:
                                try:
                                    model = genai.GenerativeModel(nome)
                                    st.info(f"✅ {nome}")
                                    break
                                except:
                                    continue

                            if not model:
                                st.error("❌ Modelo indisponível")
                                st.stop()

                            prompt = f"""Analista da Prefeitura de Contagem.

PROCESSO: {dados[1]}
RT: {dados[2]}
REQUERENTE: {dados[3]}
USO: {dados[5]}
TIPOLOGIA: {dados[6]}
ÁREA: {dados[7]}m²
PROTOCOLO: {datetime.strptime(dados[8], '%Y-%m-%d').strftime('%d/%m/%Y')}

LEGISLAÇÃO:
{txt_leg[:4000]}

REGRAS:
{regras}

PROJETO:
{txt_proj[:6000]}

Analise:

## ✅ CONFORMIDADES

## ❌ NÃO CONFORMIDADES

## ⚠️ ATENÇÃO

## 🔧 RECOMENDAÇÕES

## 📊 PARECER
APROVADO ou REPROVADO
"""

                            resp = model.generate_content(prompt)

                            texto = resp.text.upper()
                            if "APROVADO" in texto and "REPROVADO" not in texto:
                                status = "APROVADO"
                                st.success("✅ APROVADO")
                                atualizar_status(dados[0], "Aprovado")
                            elif "REPROVADO" in texto:
                                status = "REPROVADO"
                                st.error("❌ REPROVADO")
                                atualizar_status(dados[0], "Reprovado")
                            else:
                                status = "INCONCLUSIVO"

                            st.divider()
                            st.markdown(resp.text)

                            salvar_analise(dados[0], resp.text, status)

                            rel = f"""PREFEITURA DE CONTAGEM
RELATÓRIO

Processo: {dados[1]}
Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}

{resp.text}
"""

                            st.download_button("📥 BAIXAR", rel, 
                                             f"relatorio_{dados[1].replace('.', '_')}.txt", 
                                             type="primary")

                        except Exception as e:
                            st.error(f"❌ {str(e)}")

st.divider()
st.markdown("🏛️ **Sistema de Validação** • Prefeitura de Contagem")

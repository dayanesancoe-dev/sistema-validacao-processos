import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime
import sqlite3

st.set_page_config(page_title="Sistema de Validação", page_icon="🏛️", layout="wide")

# ==================== BANCO DE DADOS ====================

@st.cache_resource
def init_db():
    conn = sqlite3.connect('processos.db', check_same_thread=False)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS processos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero TEXT UNIQUE NOT NULL,
        rt TEXT NOT NULL,
        requerente TEXT NOT NULL,
        analista TEXT NOT NULL,
        uso TEXT NOT NULL,
        tipologia TEXT NOT NULL,
        area REAL NOT NULL,
        data TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS analises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        processo_id INTEGER NOT NULL,
        resultado TEXT NOT NULL,
        status TEXT NOT NULL,
        data TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (processo_id) REFERENCES processos(id)
    )''')

    conn.commit()
    return conn

conn = init_db()

# ==================== FUNÇÕES ====================

def cadastrar(numero, rt, requerente, analista, uso, tipologia, area):
    try:
        c = conn.cursor()
        c.execute('INSERT INTO processos (numero, rt, requerente, analista, uso, tipologia, area) VALUES (?, ?, ?, ?, ?, ?, ?)',
                 (numero, rt, requerente, analista, uso, tipologia, area))
        conn.commit()
        return True, "✅ Cadastrado!"
    except:
        return False, "❌ Erro!"

def listar():
    c = conn.cursor()
    c.execute('SELECT * FROM processos ORDER BY data DESC')
    return c.fetchall()

def deletar(pid):
    try:
        c = conn.cursor()
        c.execute('DELETE FROM analises WHERE processo_id = ?', (pid,))
        c.execute('DELETE FROM processos WHERE id = ?', (pid,))
        conn.commit()
        return True
    except:
        return False

def salvar_analise(pid, resultado, status):
    try:
        c = conn.cursor()
        c.execute('INSERT INTO analises (processo_id, resultado, status) VALUES (?, ?, ?)', (pid, resultado, status))
        conn.commit()
        return True
    except:
        return False

def buscar_analises(pid):
    c = conn.cursor()
    c.execute('SELECT * FROM analises WHERE processo_id = ? ORDER BY data DESC', (pid,))
    return c.fetchall()

# ==================== INTERFACE ====================

st.title("🏛️ Sistema de Validação de Processos")
st.markdown("**Prefeitura de Contagem**")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configurações")
    api_key = st.text_input("API Key Gemini:", type="password")

    if api_key:
        st.success("✅ OK")
    else:
        st.warning("⚠️ Configure API")

    st.divider()
    st.metric("Processos", len(listar()))

# Abas
tab1, tab2, tab3 = st.tabs(["📝 Cadastrar", "📋 Gerenciar", "🤖 Analisar"])

# ==================== ABA 1: CADASTRAR ====================
with tab1:
    st.header("📝 Novo Processo")

    with st.form("form_cad"):
        col1, col2 = st.columns(2)

        with col1:
            num = st.text_input("Número *", key="cad_num")
            rt = st.text_input("RT *", key="cad_rt")
            req = st.text_input("Requerente *", key="cad_req")
            ana = st.text_input("Analista *", key="cad_ana")

        with col2:
            uso = st.selectbox("Uso *", ["", "Residencial", "Comercial", "Industrial", "Misto"], key="cad_uso")
            tip = st.selectbox("Tipologia *", ["", "Casa", "Sobrado", "Edifício", "Galpão", "Loja"], key="cad_tip")
            area = st.number_input("Área (m²) *", min_value=0.0, step=0.01, key="cad_area")

        if st.form_submit_button("✅ Cadastrar", type="primary"):
            if num and rt and req and ana and uso and tip and area > 0:
                ok, msg = cadastrar(num, rt, req, ana, uso, tip, area)
                if ok:
                    st.success(msg)
                    st.balloons()
                else:
                    st.error(msg)
            else:
                st.error("❌ Preencha todos os campos!")

# ==================== ABA 2: GERENCIAR ====================
with tab2:
    st.header("📋 Processos")

    procs = listar()

    if not procs:
        st.info("📭 Nenhum processo")
    else:
        for p in procs:
            with st.expander(f"📄 {p[1]} - {p[3]}"):
                st.write(f"**RT:** {p[2]}")
                st.write(f"**Analista:** {p[4]}")
                st.write(f"**Uso:** {p[5]} | **Tipologia:** {p[6f"**Área:** {p[7]}m²")

                analises = buscar_analises(p[0])
                if analises:
                    st.divider()
                    for a in analises:
                        icone = "✅" if a[3] == "APROVADO" else "❌"
                        st.write(f"{icone} {a[4]}")

                if st.button("🗑️", key=f"del_{p[0]}"):
                    if deletar(p[0]):
                        st.success("Deletado!")
                        st.rerun()

# ==================== ABA 3: ANALISAR ====================
with tab3:
    st.header("🤖 Análise com IA")

    if not api_key:
        st.warning("⚠️ Configure API Key")
        st.stop()

    procs = listar()

    if not procs:
        st.info("📭 Cadastre um processo")
        st.stop()

    proc_sel = st.selectbox("Processo:", [f"{p[1]} - {p[3]}" for p in procs], key="anal_sel")

    if proc_sel:
        num_proc = proc_sel.split(" - ")[0]

        # Buscar dados
        c = conn.cursor()
        c.execute('SELECT * FROM processos WHERE numero = ?', (num_proc,))
        dados = c.fetchone()

        if dados:
            with st.expander("📋 Dados", expanded=True):
                col1, col2, col3 = st.columns(3)
                col1.metric("Número", dados[1])
                col2.metric("Uso", dados[5])
                col3.metric("Área", f"{dados[7]}m²")

            st.divider()

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("📐 PDFs Projeto")
                proj = st.file_uploader("Anexar", type=['pdf'], accept_multiple_files=True, key="anal_proj")

            with col2:
                st.subheader("📜 PDFs Legislação")
                leg = st.file_uploader("Anexar", type=['pdf'], accept_multiple_files=True, key="anal_leg")

            st.divider()
            regras = st.text_area("📏 Regras:", height=150, key="anal_regras", 
                                 placeholder="Ex:\nArt. 10 - Área mínima 50m²")

            st.divider()

            if st.button("🔍 ANALISAR", type="primary"):
                if not proj or not leg or not regras:
                    st.error("❌ Anexe PDFs e regras!")
                else:
                    with st.spinner("🤖 Analisando..."):
                        try:
                            genai.configure(api_key=api_key)

                            # Extrair textos
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

                            # Criar modelo
                            model = None
                            for nome in ['gemini-1.5-flash', 'gemini-pro', 'gemini-1.5-pro']:
                                try:
                                    model = genai.GenerativeModel(nome)
                                    st.info(f"✅ {nome}")
                                    break
                                except:
                                    continue

                            if not model:
                                st.error("❌ Nenhum modelo disponível")
                                st.stop()

                            # Prompt
                            prompt = f"""Analista Prefeitura de Contagem.

PROCESSO: {dados[1]}
RT: {dados[2]}
REQUERENTE: {dados[3]}
USO: {dados[5]}
ÁREA: {dados[7]}m²

LEGISLAÇÃO:
{txt_leg[:4000]}

REGRAS:
{regras}

PROJETO:
{txt_proj[:6000]}

Analise:

## ✅ CONFORMIDADES
(cite artigos)

## ❌ NÃO CONFORMIDADES
(cite artigos)

## ⚠️ ATENÇÃO

## 🔧 RECOMENDAÇÕES

## 📊 PARECER
APROVADO ou REPROVADO
"""

                            resp = model.generate_content(prompt)

                            # Status
                            texto = resp.text.upper()
                            if "APROVADO" in texto and "REPROVADO" not in texto:
                                status = "APROVADO"
                                st.success("✅ APROVADO")
                            elif "REPROVADO" in texto:
                                status = "REPROVADO"
                                st.error("❌ REPROVADO")
                            else:
                                status = "INCONCLUSIVO"

                            st.divider()
                            st.markdown(resp.text)

                            # Salvar
                            salvar_analise(dados[0], resp.text, status)

                            # Download
                            rel = f"""PREFEITURA DE CONTAGEM
RELATÓRIO

Processo: {dados[1]}
RT: {dados[2]}
Requerente: {dados[3]}
Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}

{resp.text}
"""

                            st.download_button("📥 BAIXAR", rel, f"relatorio_{dados[1].replace('.', '_')}.txt", type="primary")

                        except Exception as e:
                            st.error(f"❌ {str(e)}")

st.divider()
st.markdown("🏛️ **Sistema de Validação** • Prefeitura de Contagem")

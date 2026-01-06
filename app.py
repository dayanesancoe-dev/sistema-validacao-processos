import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime
import sqlite3
import os

st.set_page_config(page_title="Sistema de Validação", page_icon="🏛️", layout="wide")

# ==================== BANCO DE DADOS ====================

def reset_database():
    """Reseta o banco de dados"""
    if os.path.exists('processos.db'):
        os.remove('processos.db')
    return init_db()

@st.cache_resource
def init_db():
    """Inicializa o banco de dados"""
    try:
        conn = sqlite3.connect('processos.db', check_same_thread=False)
        c = conn.cursor()

        # Criar tabela de processos
        c.execute('''CREATE TABLE IF NOT EXISTS processos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT UNIQUE NOT NULL,
            rt TEXT NOT NULL,
            requerente TEXT NOT NULL,
            analista TEXT NOT NULL,
            uso TEXT NOT NULL,
            tipologia TEXT NOT NULL,
            area REAL NOT NULL,
            data_cadastro TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

        # Criar tabela de análises
        c.execute('''CREATE TABLE IF NOT EXISTS analises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_id INTEGER NOT NULL,
            resultado TEXT NOT NULL,
            status TEXT NOT NULL,
            data_analise TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (processo_id) REFERENCES processos(id)
        )''')

        conn.commit()
        return conn
    except Exception as e:
        st.error(f"Erro ao inicializar banco: {str(e)}")
        return None

conn = init_db()

# ==================== FUNÇÕES ====================

def cadastrar(numero, rt, requerente, analista, uso, tipologia, area):
    """Cadastra novo processo"""
    if not conn:
        return False, "❌ Erro de conexão com banco!"
    try:
        c = conn.cursor()
        c.execute('''INSERT INTO processos 
                    (numero, rt, requerente, analista, uso, tipologia, area) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                 (numero, rt, requerente, analista, uso, tipologia, area))
        conn.commit()
        return True, "✅ Cadastrado!"
    except sqlite3.IntegrityError:
        return False, "❌ Processo já existe!"
    except Exception as e:
        return False, f"❌ Erro: {str(e)}"

def listar():
    """Lista todos os processos"""
    if not conn:
        return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM processos ORDER BY id DESC')
        return c.fetchall()
    except Exception as e:
        st.error(f"Erro ao listar: {str(e)}")
        return []

def buscar_por_numero(numero):
    """Busca processo por número"""
    if not conn:
        return None
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM processos WHERE numero = ?', (numero,))
        return c.fetchone()
    except Exception as e:
        st.error(f"Erro ao buscar: {str(e)}")
        return None

def deletar(pid):
    """Deleta processo"""
    if not conn:
        return False
    try:
        c = conn.cursor()
        c.execute('DELETE FROM analises WHERE processo_id = ?', (pid,))
        c.execute('DELETE FROM processos WHERE id = ?', (pid,))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao deletar: {str(e)}")
        return False

def salvar_analise(pid, resultado, status):
    """Salva análise"""
    if not conn:
        return False
    try:
        c = conn.cursor()
        c.execute('INSERT INTO analises (processo_id, resultado, status) VALUES (?, ?, ?)', 
                 (pid, resultado, status))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {str(e)}")
        return False

def buscar_analises(pid):
    """Busca análises"""
    if not conn:
        return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM analises WHERE processo_id = ? ORDER BY id DESC', (pid,))
        return c.fetchall()
    except Exception as e:
        return []

# ==================== INTERFACE ====================

st.title("🏛️ Sistema de Validação de Processos")
st.markdown("**Prefeitura de Contagem**")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configurações")
    api_key = st.text_input("API Key Gemini:", type="password")

    if api_key:
        st.success("✅ API OK")
    else:
        st.warning("⚠️ Configure API")

    st.divider()
    st.metric("Processos", len(listar()))

    st.divider()
    if st.button("🔄 Resetar Banco", help="Use apenas se houver erros"):
        reset_database()
        st.success("Banco resetado!")
        st.rerun()

# Abas
tab1, tab2, tab3 = st.tabs(["📝 Cadastrar", "📋 Gerenciar", "🤖 Analisar"])

# ==================== ABA 1 ====================
with tab1:
    st.header("📝 Cadastrar")

    with st.form("form_cad"):
        col1, col2 = st.columns(2)

        with col1:
            num = st.text_input("Número *")
            rt = st.text_input("RT *")
            req = st.text_input("Requerente *")
            ana = st.text_input("Analista *")

        with col2:
            uso = st.selectbox("Uso *", ["", "Residencial", "Comercial", "Industrial", "Misto"])
            tip = st.selectbox("Tipologia *", ["", "Casa", "Sobrado", "Edifício", "Galpão"])
            area = st.number_input("Área (m²) *", min_value=0.0, step=0.01)

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

# ==================== ABA 2 ====================
with tab2:
    st.header("📋 Gerenciar")

    procs = listar()

    if not procs:
        st.info("📭 Nenhum processo")
    else:
        for p in procs:
            with st.expander(f"📄 {p[1]} - {p[3]}"):
                st.write(f"**RT:** {p[2]}")
                st.write(f"**Analista:** {p[4]}")
                st.write(f"**Uso:** {p[5]} | **Tipologia:** {p[6]}")
                st.write(f"**Área:** {p[7]}m²")

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

# ==================== ABA 3 ====================
with tab3:
    st.header("🤖 Analisar")

    if not api_key:
        st.warning("⚠️ Configure API Key")
        st.stop()

    procs = listar()

    if not procs:
        st.info("📭 Cadastre um processo")
        st.stop()

    proc_sel = st.selectbox("Processo:", [f"{p[1]} - {p[3]}" for p in procs])

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
                    with st.spinner(" Analisando..."):
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
ÁREA: {dados[7]}m²

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
                            elif "REPROVADO" in texto:
                                status = "REPROVADO"
                                st.error("❌ REPROVADO")
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

                            st.download_button("📥 BAIXAR", rel, f"relatorio_{dados[1].replace('.', '_')}.txt", type="primary")

                        except Exception as e:
                            st.error(f"❌ {str(e)}")

st.divider()
st.markdown("🏛️ **Sistema de Validação** • Prefeitura de Contagem")

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
        return False, "❌ Erro ao cadastrar!"

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
st.markdown("**Prefeitura de Contagem** — Liberação de Alvarás")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configurações")
    api_key = st.text_input("API Key Gemini:", type="password")

    if api_key:
        st.success("✅ API OK")
    else:
        st.warning("⚠️ Configure API Key")

    st.divider()
    st.metric("Total de Processos", len(listar()))

# Abas
tab1, tab2, tab3 = st.tabs(["📝 Cadastrar", "📋 Gerenciar", "🤖 Analisar"])

# ==================== ABA 1: CADASTRAR ====================
with tab1:
    st.header("📝 Cadastrar Novo Processo")

    with st.form("form_cadastro"):
        col1, col2 = st.columns(2)

        with col1:
            num = st.text_input("Número do Processo *", key="cad_num")
            rt = st.text_input("Responsável Técnico *", key="cad_rt")
            req = st.text_input("Requerente *", key="cad_req")
            ana = st.text_input("Analista *", key="cad_ana")

        with col2:
            uso = st.selectbox("Uso *", ["", "Residencial", "Comercial", "Industrial", "Misto", "Institucional"], key="cad_uso")
            tip = st.selectbox("Tipologia *", ["", "Casa", "Sobrado", "Edifício", "Galpão", "Loja", "Sala Comercial"], key="cad_tip")
            area = st.number_input("Área Construída (m²) *", min_value=0.0, step=0.01, key="cad_area")

        st.markdown("*Campos obrigatórios")

        if st.form_submit_button("✅ Cadastrar Processo", type="primary", use_container_width=True):
            if num and rt and req and ana and uso and tip and area > 0:
                ok, msg = cadastrar(num, rt, req, ana, uso, tip, area)
                if ok:
                    st.success(msg)
                    st.balloons()
                else:
                    st.error(msg)
            else:
                st.error("❌ Preencha todos os campos obrigatórios!")

# ==================== ABA 2: GERENCIAR ====================
with tab2:
    st.header("📋 Gerenciar Processos")

    procs = listar()

    if not procs:
        st.info("📭 Nenhum processo cadastrado")
    else:
        st.write(f"**Total: {len(procs)} processo(s)**")
        st.divider()

        for p in procs:
            with st.expander(f"📄 {p[1]} - {p[3]}"):
                col_info, col_btn = st.columns([4, 1])

                with col_info:
                    st.write(f"**RT:** {p[2]}")
                    st.write(f"**Requerente:** {p[3]}")
                    st.write(f"**Analista:** {p[4]}")
                    st.write(f"**Uso:** {p[5]} | **Tipologia:** {p[6]}")
                    st.write(f"**Área:** {p[7]}m²")
                    st.write(f"**Cadastrado em:** {p[8]}")

                    analises = buscar_analises(p[0])
                    if analises:
                        st.divider()
                        st.write("**📊 Histórico de Análises:**")
                        for a in analises:
                            icone = "✅" if a[3] == "APROVADO" else "❌"
                            st.write(f"{icone} {a[4]} - **{a[3]}**")

                with col_btn:
                    if st.button("🗑️", key=f"del_{p[0]}", help="Deletar processo"):
                        if deletar(p[0]):
                            st.success("✅ Deletado!")
                            st.rerun()
                        else:
                            st.error("❌ Erro!")

# ==================== ABA 3: ANALISAR ====================
with tab3:
    st.header("🤖 Análise Inteligente com IA")

    if not api_key:
        st.warning("⚠️ Configure sua API Key na barra lateral para usar análise com IA")
        st.stop()

    procs = listar()

    if not procs:
        st.info("📭 Cadastre um processo primeiro na aba 'Cadastrar'")
        st.stop()

    proc_sel = st.selectbox("Selecione o Processo:", [f"{p[1]} - {p[3]}" for p in procs], key="anal_sel")

    if proc_sel:
        num_proc = proc_sel.split(" - ")[0]

        c = conn.cursor()
        c.execute('SELECT * FROM processos WHERE numero = ?', (num_proc,))
        dados = c.fetchone()

        if dados:
            with st.expander("📋 Dados do Processo", expanded=True):
                col1, col2, col3 = st.columns(3)
                col1.metric("Número", dados[1])
                col2.metric("Uso", dados[5])
                col3.metric("Área", f"{dados[7]}m²")

                st.write(f"**RT:** {dados[2]}")
                st.write(f"**Requerente:** {dados[3]}")
                st.write(f"**Analista:** {dados[4]}")
                st.write(f"**Tipologia:** {dados[6]}")

            st.divider()

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("📐 PDFs do Projeto")
                proj = st.file_uploader("Anexe os PDFs do projeto", type=['pdf'], accept_multiple_files=True, key="anal_proj")
                if proj:
                    st.success(f"✅ {len(proj)} arquivo(s) anexado(s)")

            with col2:
                st.subheader("📜 PDFs da Legislação")
                leg = st.file_uploader("Anexe os PDFs da legislação", type=['pdf'], accept_multiple_files=True, key="anal_leg")
                if leg:
                    st.success(f"✅ {len(leg)} arquivo(s) anexado(s)")

            st.divider()
            st.subheader("📏 Regras a Verificar")
            regras = st.text_area("Digite as regras da legislação (uma por linha):", height=150, key="anal_regras",
                                 placeholder="Exemplo:\nArt. 10 - Área mínima de 50m²\nArt. 15 - Recuo frontal de 5m")

            st.divider()

            if st.button("🔍 ANALISAR PROJETO COM IA", type="primary", use_container_width=True):
                if not proj or not leg or not regras:
                    st.error("❌ Anexe os PDFs do projeto, da legislação e digite as regras!")
                else:
                    with st.spinner("🤖 Analisando projeto com Inteligência Artificial..."):
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

                            # Tentar modelos
                            model = None
                            for nome in ['gemini-1.5-flash', 'gemini-pro', 'gemini-1.5-pro']:
                                try:
                                    model = genai.GenerativeModel(nome)
                                    st.info(f"✅ Usando modelo: {nome}")
                                    break
                                except:
                                    continue

                            if not model:
                                st.error("❌ Nenhum modelo disponível. Verifique sua API Key.")
                                st.stop()

                            # Prompt
                            prompt = f"""Você é um analista técnico especializado da Prefeitura de Contagem - MG.

DADOS DO PROCESSO:
- Número: {dados[1]}
- RT: {dados[2]}
- Requerente: {dados[3]}
- Analista: {dados[4]}
- Uso: {dados[5]}
- Tipologia: {dados[6]}
- Área: {dados[7]}m²

LEGISLAÇÃO MUNICIPAL:
{txt_leg[:4000]}

REGRAS ESPECÍFICAS A VERIFICAR:
{regras}

PROJETO ARQUITETÔNICO:
{txt_proj[:6000]}

INSTRUÇÕES:
Analise detalhadamente o projeto e verifique conformidade com a legislação.
SEMPRE cite o artigo específico da lei.

FORMATO DA RESPOSTA:

## ✅ CONFORMIDADES
(liste o que está conforme citando artigos)

## ❌ NÃO CONFORMIDADES
(liste violações citando artigos e localizando no projeto)

## ⚠️ PONTOS DE ATENÇÃO
(itens que precisam verificação adicional)

## 🔧 RECOMENDAÇÕES
(sugestões de correção)

## 📊 PARECER TÉCNICO FINAL
APROVADO ou REPROVADO (justifique citando artigos)
"""

                            resp = model.generate_content(prompt)

                            # Determinar status
                            texto = resp.text.upper()
                            if "APROVADO" in texto and "REPROVADO" not in texto:
                                status = "APROVADO"
                                st.success("✅ PROJETO APROVADO")
                            elif "REPROVADO" in texto:
                                status = "REPROVADO"
                                st.error("❌ PROJETO REPROVADO")
                            else:
                                status = "INCONCLUSIVO"
                                st.warning("⚠️ ANÁLISE INCONCLUSIVA")

                            st.divider()
                            st.markdown(resp.text)

                            # Salvar análise
                            salvar_analise(dados[0], resp.text, status)

                            # Download
                            relatorio = f"""PREFEITURA DE CONTAGEM - MG
RELATÓRIO DE ANÁLISE TÉCNICA

Processo: {dados[1]}
RT: {dados[2]}
Requerente: {dados[3]}
Analista: {dados[4]}
Uso: {dados[5]}
Tipologia: {dados[6]}
Área: {dados[7]}m²
Data: {datetime.now().strftime('%d/%m/%Y às %H:%M')}

{'='*80}

{resp.text}

{'='*80}
Relatório gerado por IA (Google Gemini)
Sistema de Validação - Prefeitura de Contagem
"""

                            st.divider()
                            st.download_button(
                                "📥 BAIXAR RELATÓRIO COMPLETO",
                                relatorio,
                                f"relatorio_{dados[1].replace('.', '_')}.txt",
                                type="primary",
                                use_container_width=True
                            )

                        except Exception as e:
                            st.error(f"❌ Erro durante a análise: {str(e)}")

st.divider()
st.markdown("---")
st.markdown("🏛️ **Sistema de Validação com IA** • Prefeitura de Contagem")

import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime, timedelta
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

        # Tabela de processos
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

        # Tabela de análises
        c.execute('''CREATE TABLE IF NOT EXISTS analises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_id INTEGER NOT NULL,
            resultado TEXT NOT NULL,
            status TEXT NOT NULL,
            data_analise TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (processo_id) REFERENCES processos(id)
        )''')

        # NOVA TABELA: Tramitação
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
        st.error(f"Erro ao inicializar banco: {str(e)}")
        return None

conn = init_db()

# ==================== FUNÇÕES ====================

def cadastrar(numero, rt, requerente, analista, uso, tipologia, area):
    """Cadastra novo processo"""
    if not conn:
        return False, "❌ Erro de conexão!"
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
        c.execute('DELETE FROM tramitacao WHERE processo_id = ?', (pid,))
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

# ==================== FUNÇÕES DE TRAMITAÇÃO ====================

def registrar_tramitacao(processo_id, setor, data_entrada, data_saida, observacao):
    """Registra movimentação do processo"""
    if not conn:
        return False
    try:
        c = conn.cursor()
        c.execute('''INSERT INTO tramitacao 
                    (processo_id, setor, data_entrada, data_saida, observacao) 
                    VALUES (?, ?, ?, ?, ?)''',
                 (processo_id, setor, data_entrada, data_saida, observacao))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao registrar: {str(e)}")
        return False

def buscar_tramitacao(processo_id):
    """Busca histórico de tramitação"""
    if not conn:
        return []
    try:
        c = conn.cursor()
        c.execute('''SELECT * FROM tramitacao 
                    WHERE processo_id = ? 
                    ORDER BY data_entrada DESC''', (processo_id,))
        return c.fetchall()
    except Exception as e:
        return []

def calcular_tempo_setor(data_entrada, data_saida):
    """Calcula tempo em dias entre duas datas"""
    try:
        if not data_saida:
            # Se não tem data de saída, calcula até hoje
            data_saida = datetime.now().strftime('%Y-%m-%d')

        entrada = datetime.strptime(data_entrada, '%Y-%m-%d')
        saida = datetime.strptime(data_saida, '%Y-%m-%d')
        dias = (saida - entrada).days
        return dias if dias >= 0 else 0
    except:
        return 0

def estatisticas_tramitacao(processo_id):
    """Calcula estatísticas de tramitação"""
    tramitacoes = buscar_tramitacao(processo_id)

    if not tramitacoes:
        return None

    stats = {}
    total_dias = 0

    for t in tramitacoes:
        setor = t[2]
        dias = calcular_tempo_setor(t[3], t[4])

        if setor not in stats:
            stats[setor] = {'dias': 0, 'vezes': 0}

        stats[setor]['dias'] += dias
        stats[setor]['vezes'] += 1
        total_dias += dias

    return {'por_setor': stats, 'total_dias': total_dias}

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
tab1, tab2, tab3, tab4 = st.tabs(["📝 Cadastrar", "📋 Gerenciar", "📊 Tramitação", "🤖 Analisar"])

# ==================== ABA 1: CADASTRAR ====================
with tab1:
    st.header("📝 Cadastrar Processo")

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

# ==================== ABA 2: GERENCIAR ====================
with tab2:
    st.header("📋 Gerenciar Processos")

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

                if st.button("🗑️ Deletar", key=f"del_{p[0]}"):
                    if deletar(p[0]):
                        st.success("✅ Deletado!")
                        st.rerun()

# ==================== ABA 3: TRAMITAÇÃO ====================
with tab3:
    st.header("📊 Gestão de Tramitação")

    procs = listar()

    if not procs:
        st.info("📭 Cadastre um processo primeiro")
    else:
        # Seleção do processo
        proc_sel = st.selectbox("Selecione o Processo:", 
                               [f"{p[1]} - {p[3]}" for p in procs],
                               key="tram_proc_sel")

        if proc_sel:
            num_proc = proc_sel.split(" - ")[0]
            dados = buscar_por_numero(num_proc)

            if dados:
                st.divider()

                # Formulário para registrar movimentação
                st.subheader("➕ Registrar Movimentação")

                with st.form("form_tramitacao"):
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        setor = st.selectbox("Setor *", [
                            "Requerente",
                            "Analista",
                            "Fiscalização",
                            "Parecer Externo",
                            "Emissão de Alvará"
                        ])

                    with col2:
                        data_entrada = st.date_input("Data Entrada *")

                    with col3:
                        data_saida = st.date_input("Data Saída", value=None)

                    obs = st.text_area("Observação", placeholder="Ex: Retornou para correções")

                    if st.form_submit_button("✅ Registrar", type="primary"):
                        data_saida_str = data_saida.strftime('%Y-%m-%d') if data_saida else None

                        if registrar_tramitacao(
                            dados[0], 
                            setor, 
                            data_entrada.strftime('%Y-%m-%d'), 
                            data_saida_str,
                            obs
                        ):
                            st.success("✅ Movimentação registrada!")
                            st.rerun()
                        else:
                            st.error("❌ Erro ao registrar")

                st.divider()

                # Histórico de tramitação
                st.subheader("📜 Histórico de Tramitação")

                tramitacoes = buscar_tramitacao(dados[0])

                if not tramitacoes:
                    st.info("📭 Nenhuma movimentação registrada")
                else:
                    # Estatísticas
                    stats = estatisticas_tramitacao(dados[0])

                    if stats:
                        st.markdown("### 📊 Estatísticas")

                        cols = st.columns(len(stats['por_setor']) + 1)

                        for idx, (setor, dados_setor) in enumerate(stats['por_setor'].items()):
                            cols[idx].metric(
                                setor,
                                f"{dados_setor['dias']} dias",
                                f"{dados_setor['vezes']}x"
                            )

                        cols[-1].metric("TOTAL", f"{stats['total_dias']} dias")

                        st.divider()

                    # Tabela de movimentações
                    st.markdown("### 📋 Detalhamento")

                    for t in tramitacoes:
                        dias = calcular_tempo_setor(t[3], t[4])

                        col1, col2, col3, col4 = st.columns([2, 2, 2, 3])

                        col1.write(f"**{t[2]}**")
                        col2.write(f"📥 {datetime.strptime(t[3], '%Y-%m-%d').strftime('%d/%m/%Y')}")

                        if t[4]:
                            col3.write(f"📤 {datetime.strptime(t[4], '%Y-%m-%d').strftime('%d/%m/%Y')}")
                        else:
                            col3.write("📤 Em andamento")

                        col4.write(f"⏱️ **{dias} dias** {f'- {t[5]}' if t[5] else ''}")

                        st.divider()

# ==================== ABA 4: ANALISAR ====================
with tab4:
    st.header("🤖 Analisar com IA")

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

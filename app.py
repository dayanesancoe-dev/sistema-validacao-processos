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
            if 'numero' not in colunas or 'data_protocolo' not in colunas:
                c.execute('DROP TABLE IF EXISTS tramitacao')
                c.execute('DROP TABLE IF EXISTS analises')
                c.execute('DROP TABLE IF EXISTS processos')

        # Criar tabela processos COM DATA_PROTOCOLO
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

def listar():
    if not conn:
        return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM processos ORDER BY id DESC')
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

def buscar_tramitacoes(processo_id):
    if not conn:
        return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM tramitacao WHERE processo_id = ? ORDER BY data_entrada DESC', 
                 (processo_id,))
        return c.fetchall()
    except:
        return []

def calcular_dias(data_entrada, data_saida):
    try:
        entrada = datetime.strptime(data_entrada, '%Y-%m-%d')
        if data_saida:
            saida = datetime.strptime(data_saida, '%Y-%m-%d')
        else:
            saida = datetime.now()
        return (saida - entrada).days
    except:
        return 0

def estatisticas_tramitacao(processo_id):
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
    api_key = st.text_input("🔑 API Key", type="password", help="Gemini API Key")

    st.divider()

    if st.button("🔄 Resetar Banco", type="secondary"):
        reset_database()
        st.success("✅ Banco resetado!")
        st.rerun()

    st.divider()

    total_procs = len(listar())
    st.metric("📊 Total Processos", total_procs)

# ==================== ABAS ====================
tab1, tab2, tab3, tab4 = st.tabs(["📝 Cadastrar", "📋 Gerenciar", "🔄 Tramitação", "🤖 Analisar"])

# ==================== ABA 1: CADASTRAR ====================
with tab1:
    st.header("📝 Cadastrar Processo")

    with st.form("form_cadastro", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            numero = st.text_input("📄 Número do Processo *", placeholder="2024/001")
            rt = st.text_input("👷 Responsável Técnico *", placeholder="João Silva")
            requerente = st.text_input("🏢 Requerente *", placeholder="Empresa XYZ")
            analista = st.text_input("👤 Analista *", placeholder="Maria Santos")

        with col2:
            uso = st.selectbox("🏗️ Uso *", [
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
                "Aprovação Inicial",
                "Levantamento Existente",
                "Modificação de Projeto",
                "Regularização",
                "Misto",
                "RIU",
                "ERB",
                "As Built"
            ])

            area = st.number_input("📏 Área Construída (m²) *", min_value=0.0, step=0.01)
            data_protocolo = st.date_input("📅 Data do Protocolo *", value=datetime.now())

        submit = st.form_submit_button("💾 CADASTRAR", type="primary", use_container_width=True)

        if submit:
            if not numero or not rt or not requerente or not analista or area <= 0:
                st.error("❌ Preencha todos os campos obrigatórios!")
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
        st.info("📭 Nenhum processo cadastrado")
    else:
        for p in procs:
            with st.expander(f"📄 {p[1]} - {p[3]}"):
                # Modo visualização
                if f"edit_{p[0]}" not in st.session_state:
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.write(f"**RT:** {p[2]}")
                        st.write(f"**Requerente:** {p[3]}")
                        st.write(f"**Analista:** {p[4]}")
                        st.write(f"**Uso:** {p[5]} | **Tipologia:** {p[6]}")
                        st.write(f"**Área:** {p[7]}m²")
                        st.write(f"**Data Protocolo:** {p[8]}")
                        st.write(f"**Cadastrado em:** {p[9]}")

                    with col2:
                        if st.button("✏️ Editar", key=f"btn_edit_{p[0]}"):
                            st.session_state[f"edit_{p[0]}"] = True
                            st.rerun()

                    with col3:
                        if st.button("🗑️ Deletar", key=f"btn_del_{p[0]}"):
                            if deletar(p[0]):
                                st.success("✅ Deletado!")
                                st.rerun()

                    # Análises
                    analises = buscar_analises(p[0])
                    if analises:
                        st.divider()
                        st.write("**📊 Análises:**")
                        for a in analises:
                            with st.expander(f"{a[3]} - {a[4]}", expanded=False):
                                st.markdown(a[2])

                # Modo edição
                else:
                    with st.form(f"form_edit_{p[0]}"):
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

                            ed_area = st.number_input("Área", value=float(p[7]), key=f"ed_area_{p[0]}")
                            ed_data = st.date_input("Data Protocolo", 
                                                   value=datetime.strptime(p[8], '%Y-%m-%d'),
                                                   key=f"ed_data_{p[0]}")

                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("💾 Salvar", type="primary"):
                                sucesso, msg = atualizar(p[0], ed_numero, ed_rt, ed_req, ed_ana, 
                                                        ed_uso, ed_tip, ed_area, ed_data.strftime('%Y-%m-%d'))
                                if sucesso:
                                    st.success(msg)
                                    del st.session_state[f"edit_{p[0]}"]
                                    st.rerun()
                                else:
                                    st.error(msg)

                        with col2:
                            if st.form_submit_button("❌ Cancelar"):
                                del st.session_state[f"edit_{p[0]}"]
                                st.rerun()

# ==================== ABA 3: TRAMITAÇÃO ====================
with tab3:
    st.header("🔄 Tramitação")

    procs = listar()

    if not procs:
        st.info("📭 Cadastre um processo")
    else:
        processo_sel = st.selectbox("Selecione o Processo:", 
                                    [f"{p[1]} - {p[3]}" for p in procs], key="tram_sel")

        if processo_sel:
            num_processo = processo_sel.split(" - ")[0]
            processo = buscar_por_numero(num_processo)

            if processo:
                st.divider()

                # Formulário nova tramitação
                with st.form("form_tram", clear_on_submit=True):
                    st.subheader("➕ Nova Movimentação")

                    col1, col2, col3 = st.columns(3)

                    with col1:
                        setor = st.selectbox("Setor:", [
                            "Requerente",
                            "Analista",
                            "Fiscalização",
                            "Parecer Externo",
                            "Emissão de Alvará",
                            "Protocolo",
                            "Arquivo"
                        ])

                    with col2:
                        data_ent = st.date_input("Data Entrada:", value=datetime.now())

                    with col3:
                        obs = st.text_input("Observação:", placeholder="Opcional")

                    if st.form_submit_button("💾 Registrar", type="primary"):
                        if adicionar_tramitacao(processo[0], setor, data_ent.strftime('%Y-%m-%d'), obs):
                            st.success("✅ Registrado!")
                            st.rerun()

                st.divider()

                # Histórico
                trams = buscar_tramitacoes(processo[0])

                if trams:
                    st.subheader("📜 Histórico")

                    for t in trams:
                        # Modo visualização
                        if f"edit_tram_{t[0]}" not in st.session_state:
                            with st.expander(f"📍 {t[2]} - {t[3]}", expanded=False):
                                col1, col2, col3 = st.columns([3, 1, 1])

                                with col1:
                                    dias = calcular_dias(t[3], t[4])
                                    st.write(f"**Entrada:** {t[3]}")
                                    st.write(f"**Saída:** {t[4] if t[4] else 'Em andamento'}")
                                    st.write(f"**Tempo:** {dias} dias")
                                    if t[5]:
                                        st.write(f"**Obs:** {t[5]}")

                                with col2:
                                    if st.button("✏️", key=f"btn_ed_t_{t[0]}"):
                                        st.session_state[f"edit_tram_{t[0]}"] = True
                                        st.rerun()

                                with col3:
                                    if st.button("🗑️", key=f"btn_del_t_{t[0]}"):
                                        if deletar_tramitacao(t[0]):
                                            st.success("✅ Deletado!")
                                            st.rerun()

                        # Modo edição
                        else:
                            with st.form(f"form_edit_tram_{t[0]}"):
                                st.subheader(f"Editar: {t[2]}")

                                ed_setor = st.selectbox("Setor", [
                                    "Requerente", "Analista", "Fiscalização",
                                    "Parecer Externo", "Emissão de Alvará",
                                    "Protocolo", "Arquivo"
                                ], index=["Requerente", "Analista", "Fiscalização",
                                         "Parecer Externo", "Emissão de Alvará",
                                         "Protocolo", "Arquivo"].index(t[2]),
                                key=f"ed_set_t_{t[0]}")

                                ed_entrada = st.date_input("Entrada", 
                                                          value=datetime.strptime(t[3], '%Y-%m-%d'),
                                                          key=f"ed_ent_t_{t[0]}")

                                ed_saida = st.date_input("Saída", 
                                                        value=datetime.strptime(t[4], '%Y-%m-%d') if t[4] else None,
                                                        key=f"ed_sai_t_{t[0]}")

                                ed_obs = st.text_input("Observação", value=t[5] or "", key=f"ed_obs_t_{t[0]}")

                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.form_submit_button("💾 Salvar", type="primary"):
                                        if atualizar_tramitacao(t[0], ed_setor, 
                                                               ed_entrada.strftime('%Y-%m-%d'),
                                                               ed_saida.strftime('%Y-%m-%d') if ed_saida else None,
                                                               ed_obs):
                                            st.success("✅ Atualizado!")
                                            del st.session_state[f"edit_tram_{t[0]}"]
                                            st.rerun()

                                with col2:
                                    if st.form_submit_button("❌ Cancelar"):
                                        del st.session_state[f"edit_tram_{t[0]}"]
                                        st.rerun()

                    st.divider()

                    # Estatísticas
                    stats = estatisticas_tramitacao(processo[0])

                    if stats:
                        cols = st.columns(len(stats))
                        for idx, (setor, dias) in enumerate(stats.items()):
                            cols[idx].metric(setor, f"{dias} dias")

                        total = sum(stats.values())
                        st.divider()
                        st.metric("⏱️ Tempo Total", f"{total} dias")
                else:
                    st.info("📭 Nenhuma movimentação")

# ==================== ABA 4: ANALISAR ====================
with tab4:
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
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Número", dados[1])
                col2.metric("Uso", dados[5])
                col3.metric("Área", f"{dados[7]}m²")
                col4.metric("Protocolo", dados[8])

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
PROTOCOLO: {dados[8]}
RT: {dados[2]}
REQUERENTE: {dados[3]}
USO: {dados[5]}
TIPOLOGIA: {dados[6]}
ÁREA: {dados[7]}m²

LEGISLAÇÃO:
{txt_leg[:4000]}

REGRAS:
{regras}

PROJETO:
{txt_proj[:6000]}

Analise detalhadamente:

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

                            rel = f"""PREFEITURA DE CONTAGEM - MG
RELATÓRIO DE ANÁLISE

Processo: {dados[1]}
Data Protocolo: {dados[8]}
Data Análise: {datetime.now().strftime('%d/%m/%Y %H:%M')}

{resp.text}
"""

                            st.download_button("📥 BAIXAR RELATÓRIO", rel, 
                                             f"relatorio_{dados[1].replace('.', '_')}.txt", 
                                             type="primary")

                        except Exception as e:
                            st.error(f"❌ {str(e)}")

st.divider()
st.markdown("🏛️ **Sistema de Validação** • Prefeitura de Contagem")

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

        # Verificar estrutura
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processos'")
        if c.fetchone():
            c.execute("PRAGMA table_info(processos)")
            colunas = [col[1] for col in c.fetchall()]
            if 'numero' not in colunas:
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

def cadastrar(numero, rt, requerente, analista, uso, tipologia, area):
    if not conn:
        return False, "❌ Erro de conexão!"
    try:
        c = conn.cursor()
        c.execute('''INSERT INTO processos (numero, rt, requerente, analista, uso, tipologia, area) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                 (numero, rt, requerente, analista, uso, tipologia, area))
        conn.commit()
        return True, "✅ Cadastrado!"
    except sqlite3.IntegrityError:
        return False, "❌ Processo já existe!"
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

# ==================== FUNÇÕES TRAMITAÇÃO ====================

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
    """Atualiza tramitação existente"""
    if not conn:
        return False
    try:
        c = conn.cursor()
        c.execute('''UPDATE tramitacao 
                    SET setor = ?, data_entrada = ?, data_saida = ?, observacao = ?
                    WHERE id = ?''',
                 (setor, data_entrada, data_saida, observacao, tram_id))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar: {str(e)}")
        return False

def deletar_tramitacao(tram_id):
    """Deleta tramitação"""
    if not conn:
        return False
    try:
        c = conn.cursor()
        c.execute('DELETE FROM tramitacao WHERE id = ?', (tram_id,))
        conn.commit()
        return True
    except:
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

def calcular_tempo(data_entrada, data_saida):
    try:
        entrada = datetime.strptime(data_entrada, '%Y-%m-%d')
        if data_saida:
            saida = datetime.strptime(data_saida, '%Y-%m-%d')
        else:
            saida = datetime.now()
        diff = (saida - entrada).days
        return diff
    except:
        return 0

def estatisticas_tramitacao(processo_id):
    tramitacoes = listar_tramitacao(processo_id)
    if not tramitacoes:
        return {}

    stats = {}
    for t in tramitacoes:
        setor = t[2]
        tempo = calcular_tempo(t[3], t[4])
        if setor not in stats:
            stats[setor] = 0
        stats[setor] += tempo

    return stats

# ==================== INTERFACE ====================

st.title("🏛️ Sistema de Validação de Processos")
st.markdown("**Prefeitura de Contagem** — Setor de Liberação de Alvarás")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configurações")
    api_key = st.text_input("API Key Gemini:", type="password")

    if api_key:
        st.success("✅ API OK")
    else:
        st.warning("⚠️ Configure API")

    st.divider()

    try:
        st.metric("Processos", len(listar()))
    except:
        st.metric("Processos", 0)

    st.divider()
    if st.button("🔄 Resetar Banco"):
        reset_database()
        st.success("✅ Resetado!")
        st.rerun()

# Abas
tab1, tab2, tab3, tab4 = st.tabs(["📝 Cadastrar", "📋 Gerenciar", "🔄 Tramitação", "🤖 Analisar"])

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
            uso = st.selectbox("Uso *", [
                "",
                "Unifamiliar",
                "Multifamiliar",
                "Serviços",
                "Comércio Varejista",
                "Comércio Atacadista",
                "Indústria",
                "Misto",
                "Sem destinação específica"
            ])

            tip = st.selectbox("Tipologia *", [
                "",
                "Aprovação Inicial",
                "Levantamento Existente",
                "Modificação de Projeto",
                "Regularização",
                "Misto",
                "RIU",
                "ERB",
                "As Built"
            ])

            area = st.number_input("Área (m²) *", min_value=0.0, step=0.01)

        if st.form_submit_button("✅ Cadastrar", type="primary"):
            if num and rt and req and ana and uso and tip and area > 0:
                ok, msg = cadastrar(num, rt, req, ana, uso, tip, area)
                if ok:
                    st.success(msg)
                    processo = buscar_por_numero(num)
                    if processo:
                        adicionar_tramitacao(processo[0], "Protocolo", datetime.now().strftime('%Y-%m-%d'), "Cadastro inicial")
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
                st.write(f"**Número:** {p[1]}")
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

# ==================== ABA 3: TRAMITAÇÃO ====================
with tab3:
    st.header("🔄 Gestão de Tramitação")

    procs = listar()

    if not procs:
        st.info("📭 Cadastre um processo primeiro")
    else:
        proc_sel = st.selectbox("Processo:", [f"{p[1]} - {p[3]}" for p in procs], key="tram_sel")

        if proc_sel:
            num_proc = proc_sel.split(" - ")[0]
            processo = buscar_por_numero(num_proc)

            if processo:
                st.divider()

                # Adicionar nova
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
                    ], key="novo_setor")

                with col2:
                    data_mov = st.date_input("Data:", key="nova_data")

                with col3:
                    obs = st.text_input("Observação:", key="nova_obs")

                if st.button("✅ Registrar", type="primary"):
                    if adicionar_tramitacao(processo[0], setor, data_mov.strftime('%Y-%m-%d'), obs):
                        st.success("✅ Registrado!")
                        st.rerun()

                st.divider()
                st.subheader("📊 Histórico")

                tramitacoes = listar_tramitacao(processo[0])

                if tramitacoes:
                    for t in tramitacoes:
                        # ID da tramitação
                        tram_id = t[0]

                        # Verificar se está editando
                        if st.session_state.get(f'edit_{tram_id}', False):
                            # Modo edição
                            st.markdown(f"### ✏️ Editando Movimentação #{tram_id}")

                            col1, col2 = st.columns(2)

                            with col1:
                                edit_setor = st.selectbox("Setor:", [
                                    "Requerente", "Analista", "Fiscalização",
                                    "Parecer Externo", "Emissão de Alvará",
                                    "Protocolo", "Arquivo"
                                ], index=["Requerente", "Analista", "Fiscalização",
                                         "Parecer Externo", "Emissão de Alvará",
                                         "Protocolo", "Arquivo"].index(t[2]), 
                                key=f"edit_setor_{tram_id}")

                                edit_entrada = st.date_input("Data Entrada:", 
                                    value=datetime.strptime(t[3], '%Y-%m-%d'),
                                    key=f"edit_entrada_{tram_id}")

                            with col2:
                                edit_saida = st.date_input("Data Saída:", 
                                    value=datetime.strptime(t[4], '%Y-%m-%d') if t[4] else None,
                                    key=f"edit_saida_{tram_id}")

                                edit_obs = st.text_input("Observação:", 
                                    value=t[5] if t[5] else "",
                                    key=f"edit_obs_{tram_id}")

                            col_save, col_cancel = st.columns(2)

                            with col_save:
                                if st.button("💾 Salvar", key=f"save_{tram_id}", type="primary"):
                                    saida_str = edit_saida.strftime('%Y-%m-%d') if edit_saida else None
                                    if atualizar_tramitacao(tram_id, edit_setor, 
                                                          edit_entrada.strftime('%Y-%m-%d'),
                                                          saida_str, edit_obs):
                                        st.success("✅ Atualizado!")
                                        st.session_state[f'edit_{tram_id}'] = False
                                        st.rerun()

                            with col_cancel:
                                if st.button("❌ Cancelar", key=f"cancel_{tram_id}"):
                                    st.session_state[f'edit_{tram_id}'] = False
                                    st.rerun()

                        else:
                            # Modo visualização
                            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1, 1])

                            col1.write(f"**{t[2]}**")
                            col2.write(f"📥 {datetime.strptime(t[3], '%Y-%m-%d').strftime('%d/%m/%Y')}")

                            if t[4]:
                                col3.write(f"📤 {datetime.strptime(t[4], '%Y-%m-%d').strftime('%d/%m/%Y')}")
                            else:
                                col3.write("🔄 Em andamento")

                            tempo = calcular_tempo(t[3], t[4])
                            col4.metric("Dias", tempo)

                            # Botões editar e deletar
                            if col5.button("✏️", key=f"btn_edit_{tram_id}"):
                                st.session_state[f'edit_{tram_id}'] = True
                                st.rerun()

                            if col5.button("🗑️", key=f"btn_del_{tram_id}"):
                                if deletar_tramitacao(tram_id):
                                    st.success("✅ Deletado!")
                                    st.rerun()

                            if t[5]:
                                st.caption(f"💬 {t[5]}")

                        st.divider()

                    # Estatísticas
                    st.subheader("📈 Tempo por Setor")
                    stats = estatisticas_tramitacao(processo[0])

                    if stats:
                        cols = st.columns(len(stats))
                        for idx, (setor, dias) in enumerate(stats.items()):
                            cols[idx].metric(setor, f"{dias} dias")

                        st.divider()
                        st.metric("⏱️ Tempo Total", f"{sum(stats.values())} dias")
                else:
                    st.info("📭 Nenhuma movimentação")

# ==================== ABA 4: ANALISAR ====================
with tab4:
    st.header("🤖 Analisar com IA")

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
            regras = st.text_area("📏 Regras:", height=150)

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

                            prompt = f"""Analista Prefeitura de Contagem.

PROCESSO: {dados[1]}
USO: {dados[5]}
TIPOLOGIA: {dados[6]}
ÁREA: {dados[7]}m²

LEGISLAÇÃO:
{txt_leg[:4000]}

REGRAS:
{regras}

PROJETO:
{txt_proj[:6000]}

## ✅ CONFORMIDADES
## ❌ NÃO CONFORMIDADES
## ⚠️ ATENÇÃO
## 🔧 RECOMENDAÇÕES
## 📊 PARECER
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
{resp.text}
"""

                            st.download_button("📥 BAIXAR", rel, f"relatorio_{dados[1].replace('.', '_')}.txt", type="primary")

                        except Exception as e:
                            st.error(f"❌ {str(e)}")

st.divider()
st.markdown("🏛️ **Sistema de Validação** • Prefeitura de Contagem")

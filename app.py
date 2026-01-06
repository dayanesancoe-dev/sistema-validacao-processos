import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime
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
        return False, "❌ Erro!"
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

def atualizar(pid, numero, rt, requerente, analista, uso, tipologia, area):
    if not conn:
        return False, "❌ Erro!"
    try:
        c = conn.cursor()
        c.execute('''UPDATE processos 
                    SET numero=?, rt=?, requerente=?, analista=?, uso=?, tipologia=?, area=?
                    WHERE id=?''',
                 (numero, rt, requerente, analista, uso, tipologia, area, pid))
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

def atualizar_tramitacao(tram_id, setor, data_entrada, data_saida, obs):
    if not conn:
        return False
    try:
        c = conn.cursor()
        c.execute('''UPDATE tramitacao 
                    SET setor=?, data_entrada=?, data_saida=?, observacao=?
                    WHERE id=?''',
                 (setor, data_entrada, data_saida, obs, tram_id))
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

    try:
        st.metric("Processos", len(listar()))
    except:
        st.metric("Processos", 0)

    st.divider()
    if st.button("🔄 Resetar Banco"):
        reset_database()
        st.success("Resetado!")
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

                if f'editando_{p[0]}' not in st.session_state:
                    # Modo visualização
                    col_info, col_btn = st.columns([4, 1])

                    with col_info:
                        st.write(f"**Número:** {p[1]}")
                        st.write(f"**RT:** {p[2]}")
                        st.write(f"**Requerente:** {p[3]}")
                        st.write(f"**Analista:** {p[4]}")
                        st.write(f"**Uso:** {p[5]}")
                        st.write(f"**Tipologia:** {p[6]}")
                        st.write(f"**Área:** {p[7]}m²")

                        analises = buscar_analises(p[0])
                        if analises:
                            st.divider()
                            for a in analises:
                                icone = "✅" if a[3] == "APROVADO" else "❌"
                                st.write(f"{icone} {a[4]} - {a[3]}")

                    with col_btn:
                        if st.button("✏️", key=f"edit_{p[0]}"):
                            st.session_state[f'editando_{p[0]}'] = True
                            st.rerun()

                        if st.button("🗑️", key=f"del_{p[0]}"):
                            if deletar(p[0]):
                                st.success("Deletado!")
                                st.rerun()
                else:
                    # Modo edição
                    st.subheader("✏️ Editar Processo")

                    with st.form(f"form_edit_{p[0]}"):
                        col1, col2 = st.columns(2)

                        with col1:
                            novo_num = st.text_input("Número", value=p[1], key=f"num_{p[0]}")
                            novo_rt = st.text_input("RT", value=p[2], key=f"rt_{p[0]}")
                            novo_req = st.text_input("Requerente", value=p[3], key=f"req_{p[0]}")
                            novo_ana = st.text_input("Analista", value=p[4], key=f"ana_{p[0]}")

                        with col2:
                            novo_uso = st.selectbox("Uso", [
                                "Unifamiliar",
                                "Multifamiliar",
                                "Serviços",
                                "Comércio Varejista",
                                "Comércio Atacadista",
                                "Indústria",
                                "Misto",
                                "Sem destinação específica"
                            ], index=["Unifamiliar", "Multifamiliar", "Serviços", "Comércio Varejista", 
                                     "Comércio Atacadista", "Indústria", "Misto", "Sem destinação específica"].index(p[5]), 
                            key=f"uso_{p[0]}")

                            novo_tip = st.selectbox("Tipologia", [
                                "Aprovação Inicial",
                                "Levantamento Existente",
                                "Modificação de Projeto",
                                "Regularização",
                                "Misto",
                                "RIU",
                                "ERB",
                                "As Built"
                            ], index=["Aprovação Inicial", "Levantamento Existente", "Modificação de Projeto",
                                     "Regularização", "Misto", "RIU", "ERB", "As Built"].index(p[6]),
                            key=f"tip_{p[0]}")

                            nova_area = st.number_input("Área", value=float(p[7]), step=0.01, key=f"area_{p[0]}")

                        col_btn1, col_btn2 = st.columns(2)

                        if col_btn1.form_submit_button("💾 Salvar", type="primary"):
                            if atualizar(p[0], novo_num, novo_rt, novo_req, novo_ana, novo_uso, novo_tip, nova_area)[0]:
                                del st.session_state[f'editando_{p[0]}']
                                st.success("Atualizado!")
                                st.rerun()

                        if col_btn2.form_submit_button("❌ Cancelar"):
                            del st.session_state[f'editando_{p[0]}']
                            st.rerun()

# ==================== ABA 3: TRAMITAÇÃO ====================
with tab3:
    st.header("🔄 Tramitação")

    procs = listar()

    if not procs:
        st.info("📭 Cadastre um processo")
    else:
        proc_sel = st.selectbox("Processo:", [f"{p[1]} - {p[3]}" for p in procs], key="tram_sel")

        if proc_sel:
            num_proc = proc_sel.split(" - ")[0]
            processo = buscar_por_numero(num_proc)

            if processo:
                st.divider()
                st.subheader("➕ Nova Movimentação")

                col1, col2, col3 = st.columns(3)

                with col1:
                    setor = st.selectbox("Setor:", [
                        "Requerente",
                        "Analista",
                        "Fiscalização",
                        "Parecer Externo",
                        "Emissão de Alvará",
                        "Protocolo"
                    ], key="tram_setor")

                with col2:
                    data_mov = st.date_input("Data:", key="tram_data")

                with col3:
                    obs = st.text_input("Observação:", key="tram_obs")

                if st.button("✅ Registrar", type="primary"):
                    if adicionar_tramitacao(processo[0], setor, data_mov.strftime('%Y-%m-%d'), obs):
                        st.success("✅ Registrado!")
                        st.rerun()

                st.divider()
                st.subheader("📊 Histórico")

                tramitacoes = listar_tramitacao(processo[0])

                if tramitacoes:
                    for t in tramitacoes:

                        if f'edit_tram_{t[0]}' not in st.session_state:
                            # Modo visualização
                            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1, 1])

                            col1.write(f"**{t[2]}**")
                            col2.write(f"📥 {datetime.strptime(t[3], '%Y-%m-%d').strftime('%d/%m/%Y')}")

                            if t[4]:
                                col3.write(f"📤 {datetime.strptime(t[4], '%Y-%m-%d').strftime('%d/%m/%Y')}")
                            else:
                                col3.write("🔄 Ativo")

                            tempo = calcular_tempo(t[3], t[4])
                            col4.metric("Dias", tempo)

                            if col5.button("✏️", key=f"edit_t_{t[0]}"):
                                st.session_state[f'edit_tram_{t[0]}'] = True
                                st.rerun()

                            if t[5]:
                                st.caption(f"💬 {t[5]}")
                        else:
                            # Modo edição
                            with st.form(f"form_edit_tram_{t[0]}"):
                                col1, col2, col3 = st.columns(3)

                                setor_edit = col1.selectbox("Setor", [
                                    "Requerente", "Analista", "Fiscalização", 
                                    "Parecer Externo", "Emissão de Alvará", "Protocolo"
                                ], index=["Requerente", "Analista", "Fiscalização", 
                                         "Parecer Externo", "Emissão de Alvará", "Protocolo"].index(t[2]),
                                key=f"set_{t[0]}")

                                data_ent = col2.date_input("Entrada", value=datetime.strptime(t[3], '%Y-%m-%d'), key=f"ent_{t[0]}")

                                if t[4]:
                                    data_sai = col3.date_input("Saída", value=datetime.strptime(t[4], '%Y-%m-%d'), key=f"sai_{t[0]}")
                                else:
                                    data_sai = col3.date_input("Saída", value=None, key=f"sai_{t[0]}")

                                obs_edit = st.text_input("Observação", value=t[5] if t[5] else "", key=f"obs_{t[0]}")

                                col_btn1, col_btn2, col_btn3 = st.columns(3)

                                if col_btn1.form_submit_button("💾 Salvar"):
                                    if atualizar_tramitacao(
                                        t[0], 
                                        setor_edit, 
                                        data_ent.strftime('%Y-%m-%d'),
                                        data_sai.strftime('%Y-%m-%d') if data_sai else None,
                                        obs_edit
                                    ):
                                        del st.session_state[f'edit_tram_{t[0]}']
                                        st.success("Atualizado!")
                                        st.rerun()

                                if col_btn2.form_submit_button("❌ Cancelar"):
                                    del st.session_state[f'edit_tram_{t[0]}']
                                    st.rerun()

                                if col_btn3.form_submit_button("🗑️ Deletar"):
                                    if deletar_tramitacao(t[0]):
                                        del st.session_state[f'edit_tram_{t[0]}']
                                        st.success("Deletado!")
                                        st.rerun()

                        st.divider()

                    st.subheader("📈 Tempo por Setor")
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

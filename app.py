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

        # Tabela de tramitações
        c.execute('''CREATE TABLE IF NOT EXISTS tramitacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_id INTEGER NOT NULL,
            setor TEXT NOT NULL,
            data_entrada TEXT NOT NULL,
            data_saida TEXT,
            observacao TEXT,
            FOREIGN KEY (processo_id) REFERENCES processos(id)
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
        st.error(f"Erro: {str(e)}")
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
        st.error(f"Erro: {str(e)}")
        return None

def deletar(pid):
    """Deleta processo"""
    if not conn:
        return False
    try:
        c = conn.cursor()
        c.execute('DELETE FROM tramitacoes WHERE processo_id = ?', (pid,))
        c.execute('DELETE FROM analises WHERE processo_id = ?', (pid,))
        c.execute('DELETE FROM processos WHERE id = ?', (pid,))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro: {str(e)}")
        return False

def adicionar_tramitacao(processo_id, setor, data_entrada, data_saida=None, obs=""):
    """Adiciona tramitação"""
    if not conn:
        return False
    try:
        c = conn.cursor()
        c.execute('''INSERT INTO tramitacoes 
                    (processo_id, setor, data_entrada, data_saida, observacao) 
                    VALUES (?, ?, ?, ?, ?)''',
                 (processo_id, setor, data_entrada, data_saida, obs))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro: {str(e)}")
        return False

def listar_tramitacoes(processo_id):
    """Lista tramitações de um processo"""
    if not conn:
        return []
    try:
        c = conn.cursor()
        c.execute('''SELECT * FROM tramitacoes 
                    WHERE processo_id = ? 
                    ORDER BY data_entrada DESC''', (processo_id,))
        return c.fetchall()
    except Exception as e:
        return []

def atualizar_saida_tramitacao(tramitacao_id, data_saida):
    """Atualiza data de saída"""
    if not conn:
        return False
    try:
        c = conn.cursor()
        c.execute('UPDATE tramitacoes SET data_saida = ? WHERE id = ?', 
                 (data_saida, tramitacao_id))
        conn.commit()
        return True
    except Exception as e:
        return False

def calcular_dias(data_entrada, data_saida):
    """Calcula dias entre datas"""
    try:
        entrada = datetime.strptime(data_entrada, '%Y-%m-%d')
        if data_saida:
            saida = datetime.strptime(data_saida, '%Y-%m-%d')
        else:
            saida = datetime.now()
        return (saida - entrada).days
    except:
        return 0

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
    st.metric("Processos", len(listar()))

    st.divider()
    if st.button("🔄 Resetar Banco"):
        reset_database()
        st.success("Banco resetado!")
        st.rerun()

# Abas
tab1, tab2, tab3, tab4 = st.tabs(["📝 Cadastrar", "📋 Gerenciar", "🔄 Tramitação", "🤖 Analisar"])

# ==================== ABA 1: CADASTRAR ====================
with tab1:
    st.header("📝 Cadastrar Processo")

    with st.form("form_cad"):
        col1, col2 = st.columns(2)

        with col1:
            num = st.text_input("Número do Processo *")
            rt = st.text_input("Responsável Técnico *")
            req = st.text_input("Requerente *")
            ana = st.text_input("Analista *")

        with col2:
            uso = st.selectbox("Uso *", ["", "Residencial", "Comercial", "Industrial", "Misto"])
            tip = st.selectbox("Tipologia *", ["", "Casa", "Sobrado", "Edifício", "Galpão", "Loja"])
            area = st.number_input("Área (m²) *", min_value=0.0, step=0.01)

        if st.form_submit_button("✅ Cadastrar", type="primary", use_container_width=True):
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
        st.info("📭 Nenhum processo cadastrado")
    else:
        for p in procs:
            with st.expander(f"📄 {p[1]} - {p[3]}"):
                st.write(f"**RT:** {p[2]}")
                st.write(f"**AnalPerfeito! Vou criar uma nova aba para **Gestão de Tramitação** que permite registrar todas as datas de movimentação do processo e calcular automaticamente o tempo em cada setor.

---

## **📄 Código Completo Atualizado com Aba de Tramitação**

Substitua **todo o conteúdo** do `app.py`:


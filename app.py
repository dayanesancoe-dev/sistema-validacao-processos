import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime, date
import sqlite3
import os

# ==================== CONFIGURAÇÃO INICIAL ====================
st.set_page_config(page_title="Sistema de Validação", page_icon="🏛️", layout="wide")

# Tentativa segura de importar bibliotecas gráficas
try:
    import pandas as pd
    import plotly.express as px
except ImportError:
    pd = None
    px = None

# ==================== BANCO DE DADOS ====================
@st.cache_resource
def init_db():
    try:
        conn = sqlite3.connect('processos.db', check_same_thread=False)
        c = conn.cursor()
        
        # Tabelas
        c.execute('''CREATE TABLE IF NOT EXISTS processos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT UNIQUE NOT NULL,
            rt TEXT, requerente TEXT, analista TEXT, uso TEXT, 
            tipologia TEXT, area REAL, data_protocolo TEXT,
            status TEXT DEFAULT 'Protocolado',
            data_cadastro TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS tramitacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_id INTEGER, setor TEXT, data_entrada TEXT, 
            data_saida TEXT, observacao TEXT,
            FOREIGN KEY (processo_id) REFERENCES processos(id)
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS analises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_id INTEGER, resultado TEXT, status TEXT, 
            data_analise TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (processo_id) REFERENCES processos(id)
        )''')
        
        # === CORREÇÃO FORÇADA DE NOMES DE SETORES ANTIGOS ===
        updates = [
            "UPDATE tramitacao SET setor = 'Pré-análise' WHERE setor = 'Pró-análise'",
            "UPDATE tramitacao SET setor = 'Pré-análise' WHERE setor = 'Pró-Análise'",
            "UPDATE tramitacao SET setor = 'Pré-análise' WHERE setor = 'Pro-analise'",
            "UPDATE tramitacao SET setor = 'Pré-análise' WHERE setor = 'Pro-Analise'"
        ]
        for cmd in updates:
            c.execute(cmd)
            
        conn.commit()
        return conn
    except Exception as e:
        st.error(f"Erro no Banco de Dados: {e}")
        return None

conn = init_db()

# ==================== FUNÇÕES AUXILIARES ====================
def executar_query(query, params=(), commit=False):
    if not conn: return False, "Sem conexão"
    try:
        c = conn.cursor()
        c.execute(query, params)
        if commit: conn.commit()
        return True, c
    except Exception as e:
        return False, str(e)

def listar_processos():
    suc, res = executar_query('SELECT * FROM processos ORDER BY id DESC')
    return res.fetchall() if suc else []

def buscar_processo(numero_ou_id):
    query = 'SELECT * FROM processos WHERE id = ?' if isinstance(numero_ou_id, int) else 'SELECT * FROM processos WHERE numero = ?'
    suc, res = executar_query(query, (numero_ou_id,))
    return res.fetchone() if suc else None

def get_processos_df():
    if not conn: return pd.DataFrame()
    try:
        df = pd.read_sql_query("SELECT * FROM processos", conn)
        df['data_protocolo'] = pd.to_datetime(df['data_protocolo'], errors='coerce')
        return df
    except Exception:
        return pd.DataFrame()

# ==================== INTERFACE PRINCIPAL ====================
def main():
    # --- LOGIN ---
    if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
    
    if not st.session_state['logged_in']:
        st.title("🔐 Login")
        with st.form("login"):
            user = st.text_input("Usuário")
            pwd = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                admin_user = st.secrets.get("admin_user", {}).get("username", "admin")
                admin_pass = st.secrets.get("admin_user", {}).get("password", "admin")
                if user == admin_user and pwd == admin_pass:
                    st.session_state['logged_in'] = True
                    st.rerun()
                else:
                    st.error("Dados incorretos.")
        return

    # --- MENU LATERAL ---
    st.sidebar.title("🏛️ Menu")
    if st.sidebar.button("Sair"):
        st.session_state['logged_in'] = False
        st.rerun()
    st.sidebar.markdown("---")
    api_key = st.sidebar.text_input("API Key Gemini", type="password")
    if api_key: genai.configure(api_key=api_key)

    # === SEÇÃO DE DADOS E BACKUP (BARRA LATERAL) ===
    st.sidebar.markdown("---")
    st.sidebar.header("💾 Dados e Backup")
    
    if conn and pd is not None:
        # 1. Exportar Excel/CSV
        with st.sidebar.expander("📥 Exportar Planilhas"):
            df_procs = get_processos_df()
            if not df_procs.empty:
                csv_procs = df_procs.to_csv(index=False, sep=';', encoding='utf-8-sig')
                st.download_button("📄 Lista de Processos", csv_procs, "processos.csv", "text/csv")
            
            try:
                q_hist = "SELECT p.numero, t.* FROM tramitacao t JOIN processos p ON t.processo_id = p.id"
                df_hist = pd.read_sql_query(q_hist, conn)
                if not df_hist.empty:
                    csv_hist = df_hist.to_csv(index=False, sep=';', encoding='utf-8-sig')
                    st.download_button("📜 Histórico Completo", csv_hist, "historico.csv", "text/csv")
            except: pass

        # 2. Backup do Arquivo .DB
        if os.path.exists("processos.db"):
            with open("processos.db", "rb") as f:
                st.sidebar.download_button(
                    label="📦 Baixar Backup (.db)",
                    data=f,
                    file_name=f"backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db",
                    mime="application/octet-stream",
                    help="Guarde este arquivo. Ele contém TODOS os seus dados."
                )

    # --- ABAS ---
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["➕ Novo", "📝 Gerenciar", "🔄 Tramitação", "📊 Kanban", "🤖 IA", "📈 Dashboard"])

    # Variáveis Globais
    usos = ["Unifamiliar", "Multifamiliar", "Comercial", "Misto", "Industrial", "Institucional"]
    tipos = ["Aprovação Inicial", "Regularização", "Modificação", "Habite-se"]
    setores = ["Análise prévia", "Pré-análise", "Analista", "Parecer externo",

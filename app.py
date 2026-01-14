import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime, date
import sqlite3
import os

# ==================== CONFIGURAÇÃO INICIAL ====================
st.set_page_config(page_title="Sistema de Validação", page_icon="🏛️", layout="wide")

try:
    import pandas as pd
    import plotly.express as px
except ImportError:
    pd = None
    px = None

# ==================== BANCO DE DADOS ====================
@st.cache_resource
def init_db():
    conn = sqlite3.connect('processos.db', check_same_thread=False)
    c = conn.cursor()
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
    conn.commit()
    return conn

conn = init_db()

def executar_query(query, params=(), commit=False):
    try:
        c = conn.cursor()
        c.execute(query, params)
        if commit: conn.commit()
        return True, c
    except Exception as e:
        return False, str(e)

# ==================== INTERFACE ====================
def main():
    if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
    
    if not st.session_state['logged_in']:
        st.title("🔐 Login")
        with st.form("login"):
            user = st.text_input("Usuário")
            pwd = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                if (user == "admin" and pwd == "admin") or (user == "dayanecoelho" and pwd == "010559"):
                    st.session_state['logged_in'] = True
                    st.rerun()
                else:
                    st.error("Dados incorretos.")
        return

    # --- MENU LATERAL ---
    api_key = st.sidebar.text_input("API Key Gemini", type="password")
    if api_key: genai.configure(api_key=api_key)

    # --- LISTAS ATUALIZADAS ---
    usos = ["Multifamiliar", "Serviços", "Comércio Varejista", "Indústria", "Unifamiliar", "Misto", "Sem destinação específica"]
    tipos = ["Aprovação inicial", "Levantamento do existente", "Modificação de projeto", "Regularização", "Misto", "Análise RIU", "ERB"]
    setores = ["Análise prévia", "Pré-análise", "Analista", "Parecer externo", "Fiscalização", "Emissão de documentos", "Requerente"]

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["➕ Novo", "📝 Gerenciar", "🔄 Tramitação", "📊 Kanban", "🤖 IA", "📈 Dashboard"])

    # --- ABA 1: NOVO ---
    with tab1:
        with st.form("novo"):
            c1, c2 = st.columns(2)
            num = c1.text_input("Número Processo")
            uso = c1.selectbox("Uso", usos)
            tipo = c2.selectbox("Tipo de Projeto", tipos)
            area = c2.number_input("Área (m²)", min_value=0.0)
            if st.form_submit_button("Salvar"):
                executar_query('INSERT INTO processos (numero, uso, tipologia, area) VALUES (?,?,?,?)', (num, uso, tipo, area), commit=True)
                st.success("Salvo!"); st.rerun()

    # --- ABA 3: TRAMITAÇÃO ---
    with tab3:
        st.header("Tramitação")
        suc, res = executar_query("SELECT id, numero FROM processos")
        procs = res.fetchall() if suc else []
        if procs:
            dict_procs = {p[1]: p[0] for p in procs}
            sel_num = st.selectbox("Processo", list(dict_procs.keys()))
            pid = dict_procs[sel_num]

            with st.form("form_tram"):
                c1, c2 = st.columns(2)
                setor_dest = c1.selectbox("Setor Destino", setores)
                obs = c2.text_area("Observação")
                d_ent = st.date_input("Data de Entrada", value=date.today())
                inf_sai = st.checkbox("Informar Saída?")
                d_sai = st.date_input("Data de Saída") if inf_sai else None

                if st.form_submit_button("Movimentar"):
                    executar_query("UPDATE tramitacao SET data_saida=? WHERE processo_id=? AND data_saida IS NULL", (d_ent.strftime('%Y-%m-%d'), pid), commit=True)
                    val_sai = d_sai.strftime('%Y-%m-%d') if inf_sai else None
                    executar_query("INSERT INTO tramitacao (processo_id, setor, data_entrada, data_saida, observacao) VALUES (?,?,?,?,?)", (pid, setor_dest, d_ent.strftime('%Y-%m-%d'), val_sai, obs), commit=True)
                    st.success("Movimentado!"); st.rerun()

            st.divider()
            suc_h, res_h = executar_query("SELECT setor, data_entrada, data_saida, observacao FROM tramitacao WHERE processo_id=? ORDER BY data_entrada ASC", (pid,))
            if suc_h:
                hist = res_h.fetchall()
                if hist:
                    st.subheader("📜 Histórico Detalhado (Ordem Analógica)")
                    st.table(pd.DataFrame(hist, columns=["Setor", "Entrada", "Saída", "Obs"]))

    # --- ABA 5: IA ---
    with tab5:
        st.header("Análise IA")
        up_p = st.file_uploader("Projeto (PDFs)", type='pdf', accept_multiple_files=True)
        up_l = st.file_uploader("Lei (PDFs)", type='pdf', accept_multiple_files=True)
        
        if st.button("Analisar") and up_p and up_l:
            with st.spinner("Analisando documentos..."):
                try:
                    txt_p = "".join([page.extract_text() for f in up_p for page in PyPDF2.PdfReader(f).pages])
                    txt_l = "".join([page.extract_text() for f in up_l for page in PyPDF2.PdfReader(f).pages])
                    
                    # Tentativa com nomes de modelos estáveis
                    modelos = ['gemini-1.5-pro', 'gemini-1.5-flash']
                    resultado = None
                    for m in modelos:
                        try:
                            model = genai.GenerativeModel(m)
                            resultado = model.generate_content(f"Analise: LEI: {txt_l[:15000]} PROJETO: {txt_p[:15000]}")
                            break
                        except: continue
                    
                    if resultado: st.markdown(resultado.text)
                    else: st.error("Limite de cota excedido. Tente em 1 minuto.")
                except Exception as e: st.error(f"Erro: {e}")

if __name__ == "__main__":
    main()

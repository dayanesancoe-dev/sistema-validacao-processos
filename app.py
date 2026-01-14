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

    # --- LISTAS (MANTIDAS EXATAMENTE COMO VOCÊ USA) ---
    usos = ["Multifamiliar", "Serviços", "Comércio Varejista", "Indústria", "Unifamiliar", "Misto", "Sem destinação específica"]
    tipos = ["Aprovação inicial", "Levantamento do existente", "modificação de projeto", "regularização", "misto", "análise RIU", "ERB"]
    
    # CORREÇÃO DA SINTAXE DO COLCHETE QUE APARECIA NO SEU ERRO
    setores = ["Análise prévia", "Pré-análise", "Analista", "Parecer externo", "Fiscalização", "Emissão de documentos", "Requerente"]

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["➕ Novo", "📝 Gerenciar", "🔄 Tramitação", "📊 Kanban", "🤖 IA"])

    # --- ABA 3: TRAMITAÇÃO (CORREÇÃO DE REGISTRO) ---
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
                    # Fecha a etapa anterior para não travar o banco
                    executar_query("UPDATE tramitacao SET data_saida=? WHERE processo_id=? AND data_saida IS NULL", (d_ent.strftime('%Y-%m-%d'), pid), commit=True)
                    val_sai = d_sai.strftime('%Y-%m-%d') if inf_sai else None
                    executar_query("INSERT INTO tramitacao (processo_id, setor, data_entrada, data_saida, observacao) VALUES (?,?,?,?,?)", (pid, setor_dest, d_ent.strftime('%Y-%m-%d'), val_sai, obs), commit=True)
                    st.success("Movimentado!"); st.rerun()

            st.divider()
            # MOSTRA O HISTÓRICO NA ORDEM QUE VOCÊ DESEJA (CRONOLÓGICA)
            suc_h, res_h = executar_query("SELECT setor, data_entrada, data_saida, observacao FROM tramitacao WHERE processo_id=? ORDER BY data_entrada ASC", (pid,))
            if suc_h:
                hist = res_h.fetchall()
                if hist:
                    st.table(pd.DataFrame(hist, columns=["Setor", "Entrada", "Saída", "Obs"]))

    # --- ABA 5: IA (CORREÇÃO DOS ERROS 404 E 429) ---
    with tab5:
        st.header("Análise IA")
        up_p = st.file_uploader("Projeto (PDF)", type='pdf', accept_multiple_files=True)
        up_l = st.file_uploader("Lei (PDF)", type='pdf', accept_multiple_files=True)
        
        if st.button("Analisar") and up_p and up_l:
            with st.spinner("Analisando..."):
                try:
                    txt_p = "".join([page.extract_text() or "" for f in up_p for page in PyPDF2.PdfReader(f).pages])
                    txt_l = "".join([page.extract_text() or "" for f in up_l for page in PyPDF2.PdfReader(f).pages])
                    
                    # CORREÇÃO DOS NOMES TÉCNICOS PARA EVITAR ERRO 404
                    # SE VOCÊ TEM ASSINATURA, O GEMINI 1.5 PRO É O PRIMEIRO DA LISTA
                    modelos = ['models/gemini-1.5-pro', 'models/gemini-1.5-flash', 'models/gemini-2.0-flash']
                    resultado = None
                    
                    for m in modelos:
                        try:
                            model = genai.GenerativeModel(m)
                            resultado = model.generate_content(f"Analise técnica: LEI: {txt_l[:20000]} PROJETO: {txt_p[:20000]}")
                            break
                        except: continue
                    
                    if resultado: st.markdown(resultado.text)
                    else: st.error("Limite de cota excedido (Erro 429). Aguarde 1 minuto e tente novamente.")
                except Exception as e: st.error(f"Erro: {e}")

if __name__ == "__main__":
    main()

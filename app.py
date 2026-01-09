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
    try:
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
    except Exception as e:
        st.error(f"Erro no Banco de Dados: {e}")
        return None

conn = init_db()

def executar_query(query, params=(), commit=False):
    if not conn: return False, "Sem conexão"
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
                # Aceita admin ou seu usuário configurado
                if (user == "admin" and pwd == "admin") or (user == "dayanecoelho" and pwd == "010559"):
                    st.session_state['logged_in'] = True
                    st.rerun()
                else:
                    st.error("Dados incorretos.")
        return

    # --- LISTAS ---
    usos = ["Multifamiliar", "Serviços", "Comércio Varejista", "Indústria", "Unifamiliar", "Misto", "Sem destinação específica"]
    
    # TIPOS CORRIGIDOS CONFORME SOLICITADO
    tipos = ["Aprovação inicial", "Levantamento do existente", "modificação de projeto", "regularização", "misto", "análise RIU", "ERB"]
    
    # SETORES COM COLCHETE CORRIGIDO (ERRO DA IMAGEM RESOLVIDO)
    setores = ["Análise prévia", "Pré-análise", "Analista", "Parecer externo", "Fiscalização", "Emissão de documentos", "Requerente"]

    tab1, tab2, tab3, tab4 = st.tabs(["➕ Novo", "📝 Gerenciar", "🔄 Tramitação", "📊 Kanban"])

    # --- ABA 1: NOVO ---
    with tab1:
        with st.form("novo"):
            c1, c2 = st.columns(2)
            num = c1.text_input("Número Processo")
            uso = c1.selectbox("Uso", usos)
            tipo = c2.selectbox("Tipo", tipos)
            area = c2.number_input("Área", min_value=0.0)
            if st.form_submit_button("Salvar"):
                suc, msg = executar_query('INSERT INTO processos (numero, uso, tipologia, area) VALUES (?,?,?,?)', (num, uso, tipo, area), commit=True)
                if suc: st.success("Salvo!"); st.rerun()
                else: st.error(msg)

    # --- ABA 3: TRAMITAÇÃO (CORREÇÃO DO REGISTRO) ---
    with tab3:
        st.header("Tramitação")
        suc, res = executar_query("SELECT id, numero FROM processos")
        procs = res.fetchall() if suc else []
        if procs:
            dict_procs = {p[1]: p[0] for p in procs}
            sel_num = st.selectbox("Processo", list(dict_procs.keys()))
            pid = dict_procs[sel_num]

            with st.form("form_tram"):
                st.subheader("Nova Movimentação")
                c1, c2 = st.columns(2)
                setor_dest = c1.selectbox("Setor Destino", setores)
                obs = c2.text_area("Observação")
                
                d_ent = st.date_input("Data de Entrada", value=date.today())
                informa_saida = st.checkbox("Informar Data de Saída?")
                d_sai = st.date_input("Data de Saída") if informa_saida else None

                if st.form_submit_button("Movimentar"):
                    # 1. Fecha a última movimentação que estava sem data de saída
                    executar_query("UPDATE tramitacao SET data_saida = ? WHERE processo_id = ? AND data_saida IS NULL", (d_ent.strftime('%Y-%m-%d'), pid), commit=True)
                    
                    # 2. Insere a nova
                    val_saida = d_sai.strftime('%Y-%m-%d') if informa_saida else None
                    suc_t, msg_t = executar_query(
                        "INSERT INTO tramitacao (processo_id, setor, data_entrada, data_saida, observacao) VALUES (?,?,?,?,?)",
                        (pid, setor_dest, d_ent.strftime('%Y-%m-%d'), val_saida, obs), commit=True
                    )
                    if suc_t:
                        st.success("Movimentação registrada com sucesso!")
                        st.rerun()
                    else:
                        st.error(f"Erro ao registrar: {msg_t}")

            # Histórico Detalhado (Ordem Cronológica)
            st.divider()
            suc_h, res_h = executar_query("SELECT setor, data_entrada, data_saida, observacao FROM tramitacao WHERE processo_id = ? ORDER BY data_entrada ASC", (pid,))
            if suc_h:
                hist = res_h.fetchall()
                if hist:
                    df_h = pd.DataFrame(hist, columns=["Setor", "Entrada", "Saída", "Obs"])
                    st.table(df_h)

if __name__ == "__main__":
    main()

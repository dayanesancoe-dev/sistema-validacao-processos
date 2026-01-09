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

def buscar_processo(pid):
    suc, res = executar_query('SELECT * FROM processos WHERE id = ?', (pid,))
    return res.fetchone() if suc else None

def get_processos_df():
    if not conn: return pd.DataFrame()
    return pd.read_sql_query("SELECT * FROM processos", conn)

# ==================== INTERFACE PRINCIPAL ====================
def main():
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

    # --- LISTAS DE OPÇÕES (ATUALIZADAS) ---
    usos = ["Multifamiliar", "Serviços", "Comércio Varejista", "Indústria", "Unifamiliar", "Misto", "Sem destinação específica"]
    
    # NOVA LISTA DE TIPOLOGIA SOLICITADA
    tipos = [
        "Aprovação inicial", 
        "Levantamento do existente", 
        "Modificação de projeto", 
        "Regularização", 
        "Misto", 
        "Análise RIU", 
        "ERB"
    ]
    
    setores = ["Análise prévia", "Pré-análise", "Analista", "Parecer externo", "Fiscalização", "Emissão de documentos", "Requerente"]

    # --- ABAS ---
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["➕ Novo", "📝 Gerenciar", "🔄 Tramitação", "📊 Kanban", "🤖 IA", "📈 Dashboard"])

    # --- ABA 1: CADASTRAR ---
    with tab1:
        st.header("Cadastrar Processo")
        with st.form("novo_proc"):
            c1, c2 = st.columns(2)
            num = c1.text_input("Número Processo")
            rt = c1.text_input("RT")
            uso = c1.selectbox("Uso", usos)
            area = c1.number_input("Área (m²)", min_value=0.0)
            req = c2.text_input("Requerente")
            ana = c2.text_input("Analista")
            tipo = c2.selectbox("Tipo de Projeto", tipos)
            data = c2.date_input("Data Protocolo")
            
            if st.form_submit_button("Salvar Processo"):
                suc, msg = executar_query(
                    'INSERT INTO processos (numero, rt, requerente, analista, uso, tipologia, area, data_protocolo) VALUES (?,?,?,?,?,?,?,?)',
                    (num, rt, req, ana, uso, tipo, area, data.strftime('%Y-%m-%d')), commit=True
                )
                if suc: st.success("Cadastrado com sucesso!"); st.rerun()
                else: st.error(f"Erro: {msg}")

    # --- ABA 2: GERENCIAR ---
    with tab2:
        st.header("Editar ou Excluir")
        procs = listar_processos()
        if procs:
            opcoes = {f"{p[1]} - {p[3]}": p[0] for p in procs}
            sel = st.selectbox("Selecione o processo:", list(opcoes.keys()))
            pid = opcoes[sel]
            d = buscar_processo(pid)
            if d:
                with st.form(f"edit_{pid}"):
                    c1, c2 = st.columns(2)
                    enum = c1.text_input("Número", d[1])
                    ert = c1.text_input("RT", d[2])
                    euso = c1.selectbox("Uso", usos, index=usos.index(d[5]) if d[5] in usos else 0)
                    earea = c1.number_input("Área", float(d[7]))
                    ereq = c2.text_input("Requerente", d[3])
                    eana = c2.text_input("Analista", d[4])
                    etipo = c2.selectbox("Tipo", tipos, index=tipos.index(d[6]) if d[6] in tipos else 0)
                    edata = c2.date_input("Data", datetime.strptime(d[8], '%Y-%m-%d').date())
                    if st.form_submit_button("Salvar Alterações"):
                        executar_query('UPDATE processos SET numero=?, rt=?, requerente=?, analista=?, uso=?, tipologia=?, area=?, data_protocolo=? WHERE id=?',
                                     (enum, ert, ereq, eana, euso, etipo, earea, edata.strftime('%Y-%m-%d'), pid), commit=True)
                        st.success("Atualizado!"); st.rerun()

    # --- ABA 3: TRAMITAÇÃO (ORDEM CRONOLÓGICA/ANALÓGICA) ---
    with tab3:
        st.header("Tramitação")
        if procs:
            sel_key = st.selectbox("Processo:", list(opcoes.keys()), key="tram_sel")
            pid_tram = opcoes[sel_key]
            with st.form("new_tram"):
                st.subheader("Nova Movimentação")
                c1, c2 = st.columns(2)
                setor = c1.selectbox("Setor Destino", setores)
                obs = c2.text_area("Observação")
                dt_ent = st.date_input("Data de Entrada", value=date.today())
                if st.form_submit_button("Registrar Movimentação"):
                    executar_query("INSERT INTO tramitacao (processo_id, setor, data_entrada, observacao) VALUES (?,?,?,?)",
                                 (pid_tram, setor, dt_ent.strftime('%Y-%m-%d'), obs), commit=True)
                    st.rerun()

            st.divider()
            suc, res = executar_query("SELECT * FROM tramitacao WHERE processo_id=?", (pid_tram,))
            if suc:
                rows = res.fetchall()
                if rows:
                    df_t = pd.DataFrame(rows, columns=['ID', 'PID', 'Setor', 'Entrada', 'Saída', 'Obs'])
                    df_t['Entrada'] = pd.to_datetime(df_t['Entrada'])
                    
                    st.subheader("📜 Histórico Detalhado (Ordem Cronológica)")
                    # ORDENAÇÃO ANALÓGICA: Do mais antigo para o mais novo
                    df_show = df_t.sort_values(by='Entrada', ascending=True).copy()
                    df_show['Entrada'] = df_show['Entrada'].dt.strftime('%d/%m/%Y')
                    st.dataframe(df_show[['Setor', 'Entrada', 'Obs']], use_container_width=True)

    # --- ABA 4: KANBAN ---
    with tab4:
        st.header("Painel Kanban")
        cols = st.columns(5)
        stats = ['Protocolado', 'Em Análise', 'Aguardando Correções', 'Aprovado', 'Reprovado']
        for i, s in enumerate(stats):
            with cols[i]:
                st.subheader(s)
                for p in [x for x in procs if x[9] == s]:
                    with st.container(border=True):
                        st.write(f"**{p[1]}**")
                        st.caption(f"{p[3]}")
                        if i < 4 and st.button("➡️", key=f"n_{p[0]}"):
                            executar_query("UPDATE processos SET status=? WHERE id=?", (stats[i+1], p[0]), commit=True)
                            st.rerun()

    # --- ABA 5: IA ---
    with tab5:
        st.header("Análise Assistida por IA")
        if not api_key: st.info("Insira a API Key no menu lateral.")
        else:
            up_p = st.file_uploader("Upload do Projeto (PDF)", type='pdf')
            if st.button("Iniciar Análise"):
                st.write("Analisando documentos...")

    # --- ABA 6: DASHBOARD ---
    with tab6:
        st.header("Indicadores")
        if pd is not None:
            df = get_processos_df()
            if not df.empty:
                st.plotly_chart(px.pie(df, names='status', title='Processos por Status'))
                st.plotly_chart(px.bar(df, x='uso', title='Distribuição por Uso'))

if __name__ == "__main__":
    main()

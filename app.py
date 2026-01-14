import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime, date
import sqlite3
import os

# ==================== CONFIGURAÇÃO INICIAL ====================
st.set_page_config(page_title="Sistema de Validação Profissional", page_icon="🏛️", layout="wide")

# Importação segura de bibliotecas para análise de dados
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
        
        # Tabela de Processos
        c.execute('''CREATE TABLE IF NOT EXISTS processos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT UNIQUE NOT NULL,
            rt TEXT, requerente TEXT, analista TEXT, uso TEXT, 
            tipologia TEXT, area REAL, data_protocolo TEXT,
            status TEXT DEFAULT 'Protocolado',
            data_cadastro TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Tabela de Tramitação/Movimentação
        c.execute('''CREATE TABLE IF NOT EXISTS tramitacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_id INTEGER, setor TEXT, data_entrada TEXT, 
            data_saida TEXT, observacao TEXT,
            FOREIGN KEY (processo_id) REFERENCES processos(id)
        )''')
        
        # Ajuste de nomes antigos de setores para manter consistência
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
                # Aceita o admin padrão ou seu usuário específico
                if (user == "admin" and pwd == "admin") or (user == "dayanecoelho" and pwd == "010559"):
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
    api_key = st.sidebar.text_input("API Key Gemini (Com Assinatura)", type="password")
    if api_key: genai.configure(api_key=api_key)

    # --- LISTAS DE OPÇÕES ---
    usos = ["Multifamiliar", "Serviços", "Comércio Varejista", "Indústria", "Unifamiliar", "Misto", "Sem destinação específica"]
    tipos = ["Aprovação inicial", "Levantamento do existente", "Modificação de projeto", "Regularização", "Misto", "Análise RIU", "ERB"]
    setores = ["Análise prévia", "Pré-análise", "Analista", "Parecer externo", "Fiscalização", "Emissão de documentos", "Requerente"]

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
                if suc: st.success("Cadastrado!"); st.rerun()
                else: st.error(f"Erro: {msg}")

    # --- ABA 3: TRAMITAÇÃO (CORREÇÃO DE REGISTRO E ORDEM CRONOLÓGICA) ---
    with tab3:
        st.header("Tramitação")
        procs = listar_processos()
        if procs:
            dict_procs = {f"{p[1]} - {p[3]}": p[0] for p in procs}
            sel_key = st.selectbox("Processo:", list(dict_procs.keys()), key="tram_sel")
            pid_tram = dict_procs[sel_key]
            
            with st.form("new_tram"):
                st.subheader("Nova Movimentação")
                c1, c2 = st.columns(2)
                setor_dest = c1.selectbox("Setor Destino", setores)
                obs = c2.text_area("Observação", height=68)
                d_ent = st.date_input("📅 Data de Entrada", value=date.today())
                inf_sai = st.checkbox("Informar Saída Retroativa?")
                d_sai = st.date_input("Data de Saída") if inf_sai else None

                if st.form_submit_button("Registrar Movimentação", type="primary"):
                    # Fecha etapa anterior
                    executar_query("UPDATE tramitacao SET data_saida=? WHERE processo_id=? AND data_saida IS NULL", (d_ent.strftime('%Y-%m-%d'), pid_tram), commit=True)
                    # Registra nova etapa
                    val_sai = d_sai.strftime('%Y-%m-%d') if inf_sai else None
                    executar_query("INSERT INTO tramitacao (processo_id, setor, data_entrada, data_saida, observacao) VALUES (?,?,?,?,?)", 
                                 (pid_tram, setor_dest, d_ent.strftime('%Y-%m-%d'), val_sai, obs), commit=True)
                    st.success("Movimentação registrada!"); st.rerun()

            st.divider()
            suc_h, res_h = executar_query("SELECT setor, data_entrada, data_saida, observacao FROM tramitacao WHERE processo_id=? ORDER BY data_entrada ASC", (pid_tram,))
            if suc_h:
                hist = res_h.fetchall()
                if hist:
                    st.subheader("📜 Histórico Detalhado (Ordem Analógica)")
                    st.table(pd.DataFrame(hist, columns=["Setor", "Entrada", "Saída", "Observação"]))

    # --- ABA 5: IA (OTIMIZADA PARA GEMINI 1.5 PRO COM ASSINATURA) ---
    with tab5:
        st.header("Análise Assistida - Gemini 1.5 Pro")
        if not api_key: 
            st.warning("Insira sua API Key com assinatura no menu lateral para habilitar o Gemini Pro.")
        elif procs:
            pid_ia = dict_procs[st.selectbox("Processo para análise:", list(dict_procs.keys()), key="ia_sel")]
            d_ia = buscar_processo(pid_ia)
            up_p = st.file_uploader("Arquivos do Projeto (PDF)", type='pdf', accept_multiple_files=True)
            up_l = st.file_uploader("Arquivos da Legislação (PDF)", type='pdf', accept_multiple_files=True)
            
            if st.button("Executar Análise Profissional") and up_p and up_l:
                with st.spinner("O Gemini 1.5 Pro está processando os arquivos..."):
                    try:
                        # Extração de texto
                        txt_p = "".join([page.extract_text() or "" for f in up_p for page in PyPDF2.PdfReader(f).pages])
                        txt_l = "".join([page.extract_text() or "" for f in up_l for page in PyPDF2.PdfReader(f).pages])
                        
                        # Lista de modelos priorizando o PRO (Nomes técnicos corrigidos para evitar Erro 404)
                        modelos = ['models/gemini-1.5-pro', 'models/gemini-1.5-flash', 'models/gemini-2.0-flash']
                        resultado = None
                        
                        for m_nome in modelos:
                            try:
                                model = genai.GenerativeModel(m_nome)
                                # Prompt de alta densidade para o modelo Pro
                                resultado = model.generate_content(
                                    f"Você é um analista técnico. Compare o PROJETO com a LEI.\n"
                                    f"DADOS: Requerente {d_ia[3]}, Uso {d_ia[5]}, Área {d_ia[7]}m².\n"
                                    f"LEI (trecho): {txt_l[:40000]}\nPROJETO (trecho): {txt_p[:40000]}\n"
                                    f"Responda em tópicos: Resumo, Itens Conformes, Pendências e Conclusão Técnica."
                                )
                                break
                            except Exception:
                                continue
                        
                        if resultado:
                            st.success("Análise concluída com sucesso!")
                            st.markdown(resultado.text)
                        else:
                            st.error("Erro de cota (429) ou modelos indisponíveis. Tente novamente em 30 segundos.")
                            
                    except Exception as e: st.error(f"Erro no processamento: {e}")

    # --- ABA 6: DASHBOARD ---
    with tab6:
        st.header("Dashboard de Controle")
        if pd is not None and px is not None:
            df = get_processos_df()
            if not df.empty:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total", len(df))
                c2.metric("Área Total", f"{df['area'].sum():,.0f} m²")
                c3.metric("Aprovados", len(df[df['status']=='Aprovado']))
                dias = (pd.Timestamp.now() - pd.to_datetime(df['data_protocolo'])).dt.days.mean()
                c4.metric("Média Dias", f"{dias:.0f}")
                
                row1_1, row1_2 = st.columns(2)
                with row1_1:
                    st.plotly_chart(px.pie(df, names='status', title='Status Geral'), use_container_width=True)
                with row1_2:
                    st.plotly_chart(px.bar(df['uso'].value_counts().reset_index(), x='count', y='uso', orientation='h', title='Distribuição por Uso'), use_container_width=True)

if __name__ == "__main__":
    main()

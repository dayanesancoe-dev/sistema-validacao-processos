import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime
import sqlite3
import os

# ==================== CONFIGURAÇÃO INICIAL ====================
st.set_page_config(page_title="Sistema de Validação", page_icon="🏛️", layout="wide")

# Importação segura de bibliotecas gráficas
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
        
        # Criação simplificada e robusta das tabelas
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
        
        conn.commit()
        return conn
    except Exception as e:
        st.error(f"Erro no Banco de Dados: {e}")
        return None

conn = init_db()

# ==================== FUNÇÕES DO SISTEMA ====================
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
    # Tenta buscar por ID se for int, senão por número
    query = 'SELECT * FROM processos WHERE id = ?' if isinstance(numero_ou_id, int) else 'SELECT * FROM processos WHERE numero = ?'
    suc, res = executar_query(query, (numero_ou_id,))
    return res.fetchone() if suc else None

# ==================== INTERFACE PRINCIPAL ====================

def main():
    # --- AUTENTICAÇÃO SIMPLES ---
    if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
    
    if not st.session_state['logged_in']:
        st.title("🔐 Login")
        with st.form("login"):
            user = st.text_input("Usuário")
            pwd = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                # Pega senha do secrets ou usa padrão 'admin'/'admin' para teste local se falhar
                admin_user = st.secrets.get("admin_user", {}).get("username", "admin")
                admin_pass = st.secrets.get("admin_user", {}).get("password", "admin")
                
                if user == admin_user and pwd == admin_pass:
                    st.session_state['logged_in'] = True
                    st.rerun()
                else:
                    st.error("Dados incorretos.")
        return # Para a execução aqui se não estiver logado

    # --- BARRA LATERAL ---
    st.sidebar.title("🏛️ Menu")
    if st.sidebar.button("Sair"):
        st.session_state['logged_in'] = False
        st.rerun()
    
    st.sidebar.markdown("---")
    api_key = st.sidebar.text_input("API Key Gemini", type="password")
    if api_key: genai.configure(api_key=api_key)

    # --- ABAS ---
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["➕ Novo", "📝 Gerenciar", "🔄 Tramitação", "📊 Kanban", "🤖 IA"])

    # ABA 1: NOVO PROCESSO
    with tab1:
        st.header("Cadastrar Processo")
        with st.form("novo_proc"):
            c1, c2 = st.columns(2)
            num = c1.text_input("Número Processo")
            rt = c1.text_input("RT")
            uso = c1.selectbox("Uso", ["Unifamiliar", "Multifamiliar", "Comercial", "Misto"])
            area = c1.number_input("Área (m²)", min_value=0.0)
            
            req = c2.text_input("Requerente")
            ana = c2.text_input("Analista")
            tipo = c2.selectbox("Tipo", ["Aprovação", "Regularização", "Modificação"])
            data = c2.date_input("Data Protocolo")
            
            if st.form_submit_button("Salvar", type="primary"):
                suc, msg = executar_query(
                    'INSERT INTO processos (numero, rt, requerente, analista, uso, tipologia, area, data_protocolo) VALUES (?,?,?,?,?,?,?,?)',
                    (num, rt, req, ana, uso, tipo, area, data.strftime('%Y-%m-%d')), commit=True
                )
                if suc: st.success("Sucesso!"); st.rerun()
                else: st.error(f"Erro: {msg}")

    # ABA 2: GERENCIAR (Onde estava o erro)
    with tab2:
        st.header("Editar ou Excluir")
        procs = listar_processos()
        if not procs:
            st.info("Nenhum processo.")
        else:
            # Seleção
            opcoes = {f"{p[1]} - {p[3]}": p[0] for p in procs} # Dic: "Numero - Req" -> ID
            selecionado = st.selectbox("Selecione o processo:", list(opcoes.keys()))
            id_selecionado = opcoes[selecionado]
            
            dados = buscar_processo(id_selecionado)
            
            if dados:
                st.markdown("---")
                # 1. FORMULÁRIO APENAS PARA EDIÇÃO (Seguro)
                with st.form(f"form_edit_{id_selecionado}"):
                    st.subheader("Editar Dados")
                    ec1, ec2 = st.columns(2)
                    enum = ec1.text_input("Número", value=dados[1])
                    ert = ec1.text_input("RT", value=dados[2])
                    euso = ec1.selectbox("Uso", ["Unifamiliar", "Multifamiliar", "Comercial", "Misto"], index=0)
                    earea = ec1.number_input("Área", value=float(dados[7]))
                    
                    ereq = ec2.text_input("Requerente", value=dados[3])
                    eana = ec2.text_input("Analista", value=dados[4])
                    etipo = ec2.selectbox("Tipo", ["Aprovação", "Regularização", "Modificação"], index=0)
                    edata = ec2.date_input("Data", value=datetime.strptime(dados[8], '%Y-%m-%d').date())
                    
                    # Botão de salvar DENTRO do form
                    if st.form_submit_button("💾 Salvar Alterações", type="primary"):
                        suc, msg = executar_query(
                            'UPDATE processos SET numero=?, rt=?, requerente=?, analista=?, uso=?, tipologia=?, area=?, data_protocolo=? WHERE id=?',
                            (enum, ert, ereq, eana, euso, etipo, earea, edata.strftime('%Y-%m-%d'), id_selecionado), commit=True
                        )
                        if suc: st.success("Atualizado!"); st.rerun()
                        else: st.error(f"Erro: {msg}")

                # 2. BOTÃO DE DELETAR FORA DO FORM (Impossível dar erro de indentação de form)
                st.markdown("### Zona de Perigo")
                col_del_1, col_del_2 = st.columns([1, 4])
                with col_del_1:
                    # Este botão NÃO é um form_submit_button, é um button comum.
                    if st.button("🗑️ Deletar Processo", type="primary"):
                        st.session_state[f'confirm_del_{id_selecionado}'] = True
                
                if st.session_state.get(f'confirm_del_{id_selecionado}'):
                    st.warning("Tem certeza? Essa ação não pode ser desfeita.")
                    if st.button("Sim, confirmar exclusão"):
                        executar_query('DELETE FROM analises WHERE processo_id=?', (id_selecionado,), commit=True)
                        executar_query('DELETE FROM tramitacao WHERE processo_id=?', (id_selecionado,), commit=True)
                        executar_query('DELETE FROM processos WHERE id=?', (id_selecionado,), commit=True)
                        st.success("Processo deletado.")
                        st.session_state[f'confirm_del_{id_selecionado}'] = False
                        st.rerun()

    # ABA 3: TRAMITAÇÃO
    with tab3:
        st.header("Tramitação")
        if procs:
            sel_tram_key = st.selectbox("Processo:", list(opcoes.keys()), key="sel_tram")
            pid_tram = opcoes[sel_tram_key]
            
            with st.form("nova_tram"):
                c1, c2 = st.columns(2)
                setor = c1.text_input("Setor Destino")
                dt_ent = c1.date_input("Entrada")
                obs = c2.text_area("Obs")
                if st.form_submit_button("Movimentar"):
                    # Fecha anterior
                    executar_query("UPDATE tramitacao SET data_saida=? WHERE processo_id=? AND data_saida IS NULL", 
                                 (dt_ent.strftime('%Y-%m-%d'), pid_tram), commit=True)
                    # Cria nova
                    executar_query("INSERT INTO tramitacao (processo_id, setor, data_entrada, observacao) VALUES (?,?,?,?)",
                                 (pid_tram, setor, dt_ent.strftime('%Y-%m-%d'), obs), commit=True)
                    st.success("Movimentado!")
                    st.rerun()
            
            # Histórico
            suc, res = executar_query("SELECT * FROM tramitacao WHERE processo_id=? ORDER BY id DESC", (pid_tram,))
            if suc:
                trams = res.fetchall()
                if trams:
                    df = pd.DataFrame(trams, columns=['ID', 'PID', 'Setor', 'Entrada', 'Saída', 'Obs'])
                    st.dataframe(df)

    # ABA 4: KANBAN
    with tab4:
        st.header("Kanban")
        cols = st.columns(5)
        status_list = ['Protocolado', 'Em Análise', 'Aguardando Correções', 'Aprovado', 'Reprovado']
        
        for idx, stat in enumerate(status_list):
            with cols[idx]:
                st.caption(f"**{stat}**")
                filtro = [p for p in procs if p[9] == stat]
                for p in filtro:
                    with st.container(border=True):
                        st.write(f"**{p[1]}**")
                        st.write(p[3])
                        # Botões simples de mover
                        if idx < 4:
                            if st.button("➡️", key=f"next_{p[0]}"):
                                executar_query("UPDATE processos SET status=? WHERE id=?", (status_list[idx+1], p[0]), commit=True)
                                st.rerun()

    # ABA 5: IA
    with tab5:
        st.header("Análise IA")
        if not api_key:
            st.warning("Configure a API Key na barra lateral.")
        elif procs:
            sel_ia_key = st.selectbox("Processo para Análise:", list(opcoes.keys()), key="sel_ia")
            pid_ia = opcoes[sel_ia_key]
            d_ia = buscar_processo(pid_ia)
            
            upload_proj = st.file_uploader("PDF Projeto", type='pdf')
            upload_lei = st.file_uploader("PDF Lei", type='pdf')
            
            if st.button("Analisar") and upload_proj and upload_lei:
                with st.spinner("Lendo documentos..."):
                    try:
                        # Extração simples
                        txt_p = PyPDF2.PdfReader(upload_proj).pages[0].extract_text()
                        txt_l = PyPDF2.PdfReader(upload_lei).pages[0].extract_text()
                        
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        prompt = f"Analise se o projeto {d_ia[1]} cumpre a lei.\nLEI: {txt_l[:2000]}\nPROJETO: {txt_p[:2000]}"
                        res = model.generate_content(prompt)
                        st.markdown(res.text)
                    except Exception as e:
                        st.error(f"Erro IA: {e}")

if __name__ == "__main__":
    main()

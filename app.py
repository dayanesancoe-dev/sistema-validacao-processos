import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime, date
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
                admin_user = st.secrets.get("admin_user", {}).get("username", "admin")
                admin_pass = st.secrets.get("admin_user", {}).get("password", "admin")
                
                if user == admin_user and pwd == admin_pass:
                    st.session_state['logged_in'] = True
                    st.rerun()
                else:
                    st.error("Dados incorretos.")
        return

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

    # Listas Padronizadas
    usos_options = ["Unifamiliar", "Multifamiliar", "Comercial", "Misto", "Industrial", "Institucional"]
    tipologias_options = ["Aprovação Inicial", "Regularização", "Modificação", "Habite-se"]
    # LISTA ATUALIZADA DE SETORES
    setores_tramitacao = [
        "Análise prévia", 
        "Pró-análise", 
        "Analista", 
        "Parecer externo", 
        "Fiscalização", 
        "Emissão de documentos"
    ]

    # ABA 1: NOVO PROCESSO
    with tab1:
        st.header("Cadastrar Processo")
        with st.form("novo_proc"):
            c1, c2 = st.columns(2)
            num = c1.text_input("Número Processo")
            rt = c1.text_input("RT")
            uso = c1.selectbox("Uso", usos_options)
            area = c1.number_input("Área (m²)", min_value=0.0)
            
            req = c2.text_input("Requerente")
            ana = c2.text_input("Analista")
            tipo = c2.selectbox("Tipo", tipologias_options)
            data = c2.date_input("Data Protocolo")
            
            if st.form_submit_button("Salvar", type="primary"):
                suc, msg = executar_query(
                    'INSERT INTO processos (numero, rt, requerente, analista, uso, tipologia, area, data_protocolo) VALUES (?,?,?,?,?,?,?,?)',
                    (num, rt, req, ana, uso, tipo, area, data.strftime('%Y-%m-%d')), commit=True
                )
                if suc: st.success("Sucesso!"); st.rerun()
                else: st.error(f"Erro: {msg}")

    # ABA 2: GERENCIAR
    with tab2:
        st.header("Editar ou Excluir")
        procs = listar_processos()
        if not procs:
            st.info("Nenhum processo.")
        else:
            opcoes = {f"{p[1]} - {p[3]}": p[0] for p in procs}
            selecionado = st.selectbox("Selecione o processo:", list(opcoes.keys()))
            id_selecionado = opcoes[selecionado]
            dados = buscar_processo(id_selecionado)
            
            if dados:
                st.markdown("---")
                with st.form(f"form_edit_{id_selecionado}"):
                    st.subheader("Editar Dados")
                    ec1, ec2 = st.columns(2)
                    enum = ec1.text_input("Número", value=dados[1])
                    ert = ec1.text_input("RT", value=dados[2])
                    euso = ec1.selectbox("Uso", usos_options, index=usos_options.index(dados[5]) if dados[5] in usos_options else 0)
                    earea = ec1.number_input("Área", value=float(dados[7]))
                    
                    ereq = ec2.text_input("Requerente", value=dados[3])
                    eana = ec2.text_input("Analista", value=dados[4])
                    etipo = ec2.selectbox("Tipo", tipologias_options, index=tipologias_options.index(dados[6]) if dados[6] in tipologias_options else 0)
                    edata = ec2.date_input("Data", value=datetime.strptime(dados[8], '%Y-%m-%d').date())
                    
                    if st.form_submit_button("💾 Salvar Alterações", type="primary"):
                        suc, msg = executar_query(
                            'UPDATE processos SET numero=?, rt=?, requerente=?, analista=?, uso=?, tipologia=?, area=?, data_protocolo=? WHERE id=?',
                            (enum, ert, ereq, eana, euso, etipo, earea, edata.strftime('%Y-%m-%d'), id_selecionado), commit=True
                        )
                        if suc: st.success("Atualizado!"); st.rerun()
                        else: st.error(f"Erro: {msg}")

                st.markdown("### Zona de Perigo")
                col_del_1, col_del_2 = st.columns([1, 4])
                with col_del_1:
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

    # ABA 3: TRAMITAÇÃO (ATUALIZADA COM DIAS)
    with tab3:
        st.header("Tramitação")
        if procs:
            sel_tram_key = st.selectbox("Processo:", list(opcoes.keys()), key="sel_tram")
            pid_tram = opcoes[sel_tram_key]
            
            # --- FORMULÁRIO DE NOVA MOVIMENTAÇÃO ---
            with st.form("nova_tram"):
                st.subheader("Nova Movimentação")
                c1, c2 = st.columns(2)
                # Agora usa a lista fixa de setores
                setor = c1.selectbox("Para qual setor o processo vai?", setores_tramitacao)
                dt_ent = c1.date_input("Data de Entrada no Setor", value=date.today())
                obs = c2.text_area("Observação")
                
                st.caption("ℹ️ Ao movimentar, o sistema fechará automaticamente a permanência no setor anterior.")
                
                if st.form_submit_button("Movimentar Processo"):
                    # 1. Fecha o setor anterior (define data_saida como a data da nova entrada)
                    executar_query("UPDATE tramitacao SET data_saida=? WHERE processo_id=? AND data_saida IS NULL", 
                                 (dt_ent.strftime('%Y-%m-%d'), pid_tram), commit=True)
                    # 2. Cria o novo registro
                    executar_query("INSERT INTO tramitacao (processo_id, setor, data_entrada, observacao) VALUES (?,?,?,?)",
                                 (pid_tram, setor, dt_ent.strftime('%Y-%m-%d'), obs), commit=True)
                    st.success("Processo movimentado com sucesso!")
                    st.rerun()
            
            # --- TABELA DE HISTÓRICO COM CÁLCULO DE DIAS ---
            st.divider()
            st.subheader("Histórico de Movimentações")
            suc, res = executar_query("SELECT * FROM tramitacao WHERE processo_id=? ORDER BY data_entrada DESC", (pid_tram,))
            
            if suc:
                trams = res.fetchall()
                if trams:
                    # Cria DataFrame
                    df = pd.DataFrame(trams, columns=['ID', 'PID', 'Setor', 'Entrada', 'Saída', 'Obs'])
                    
                    # Converte colunas de data para datetime
                    df['Entrada'] = pd.to_datetime(df['Entrada'])
                    df['Saída'] = pd.to_datetime(df['Saída'])
                    
                    # CÁLCULO DE DIAS
                    # Se tiver data de saída: Saída - Entrada. Se não (ainda está lá): Hoje - Entrada.
                    hoje = pd.Timestamp.now().normalize()
                    
                    def calcular_dias(row):
                        inicio = row['Entrada']
                        fim = row['Saída'] if pd.notnull(row['Saída']) else hoje
                        return (fim - inicio).days

                    df['Dias no Setor'] = df.apply(calcular_dias, axis=1)
                    
                    # Formata as datas para exibir bonitinho (sem hora) e remove NaN
                    df['Entrada'] = df['Entrada'].dt.strftime('%d/%m/%Y')
                    df['Saída'] = df['Saída'].dt.strftime('%d/%m/%Y').fillna("Atual")
                    
                    # Remove colunas técnicas (ID e PID) para exibição
                    st.dataframe(df[['Setor', 'Entrada', 'Saída', 'Dias no Setor', 'Obs']], use_container_width=True)
                else:
                    st.info("Nenhuma tramitação registrada.")

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

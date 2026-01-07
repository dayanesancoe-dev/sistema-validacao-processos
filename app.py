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

def get_processos_df():
    """Retorna um DataFrame pandas com todos os processos para análise gráfica"""
    if not conn: return pd.DataFrame()
    try:
        df = pd.read_sql_query("SELECT * FROM processos", conn)
        df['data_protocolo'] = pd.to_datetime(df['data_protocolo'], errors='coerce')
        df['data_cadastro'] = pd.to_datetime(df['data_cadastro'], errors='coerce')
        return df
    except Exception:
        return pd.DataFrame()

# ==================== INTERFACE PRINCIPAL ====================

def main():
    # --- AUTENTICAÇÃO ---
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

    # --- ABAS ---
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["➕ Novo", "📝 Gerenciar", "🔄 Tramitação", "📊 Kanban", "🤖 IA", "📈 Dashboard"])

    # --- VARIÁVEIS GLOBAIS ---
    usos_options = ["Unifamiliar", "Multifamiliar", "Comercial", "Misto", "Industrial", "Institucional"]
    tipologias_options = ["Aprovação Inicial", "Regularização", "Modificação", "Habite-se"]
    setores_tramitacao = ["Análise prévia", "Pró-análise", "Analista", "Parecer externo", "Fiscalização", "Emissão de documentos"]

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
        st.header("Editar ou Excluir Processo")
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
                    st.subheader("Editar Dados Cadastrais")
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
                    st.warning("Tem certeza? Todos os históricos serão apagados.")
                    if st.button("Sim, confirmar exclusão"):
                        executar_query('DELETE FROM analises WHERE processo_id=?', (id_selecionado,), commit=True)
                        executar_query('DELETE FROM tramitacao WHERE processo_id=?', (id_selecionado,), commit=True)
                        executar_query('DELETE FROM processos WHERE id=?', (id_selecionado,), commit=True)
                        st.success("Processo deletado.")
                        st.session_state[f'confirm_del_{id_selecionado}'] = False
                        st.rerun()

    # ABA 3: TRAMITAÇÃO (ATUALIZADA COM EDIÇÃO)
    with tab3:
        st.header("Tramitação")
        if procs:
            sel_tram_key = st.selectbox("Processo:", list(opcoes.keys()), key="sel_tram")
            pid_tram = opcoes[sel_tram_key]
            
            # --- FORMULÁRIO DE NOVA MOVIMENTAÇÃO ---
            with st.form("nova_tram"):
                st.subheader("Nova Movimentação")
                c1, c2 = st.columns(2)
                setor = c1.selectbox("Setor Destino", setores_tramitacao)
                dt_ent = c1.date_input("Data Entrada no Setor", value=date.today())
                obs = c2.text_area("Observação")
                
                if st.form_submit_button("Movimentar Processo"):
                    executar_query("UPDATE tramitacao SET data_saida=? WHERE processo_id=? AND data_saida IS NULL", 
                                 (dt_ent.strftime('%Y-%m-%d'), pid_tram), commit=True)
                    executar_query("INSERT INTO tramitacao (processo_id, setor, data_entrada, observacao) VALUES (?,?,?,?)",
                                 (pid_tram, setor, dt_ent.strftime('%Y-%m-%d'), obs), commit=True)
                    st.success("Movimentado!")
                    st.rerun()
            
            st.divider()
            st.subheader("Histórico de Movimentações")
            suc, res = executar_query("SELECT * FROM tramitacao WHERE processo_id=? ORDER BY data_entrada DESC", (pid_tram,))
            
            trams_data = []
            if suc:
                trams_data = res.fetchall()
                if trams_data:
                    # Exibir Tabela
                    df = pd.DataFrame(trams_data, columns=['ID', 'PID', 'Setor', 'Entrada', 'Saída', 'Obs'])
                    df['Entrada'] = pd.to_datetime(df['Entrada'])
                    df['Saída'] = pd.to_datetime(df['Saída'])
                    hoje = pd.Timestamp.now().normalize()
                    df['Dias'] = df.apply(lambda row: ((row['Saída'] if pd.notnull(row['Saída']) else hoje) - row['Entrada']).days, axis=1)
                    
                    df_show = df.copy()
                    df_show['Entrada'] = df_show['Entrada'].dt.strftime('%d/%m/%Y')
                    df_show['Saída'] = df_show['Saída'].dt.strftime('%d/%m/%Y').fillna("Atual")
                    
                    st.dataframe(df_show[['Setor', 'Entrada', 'Saída', 'Dias', 'Obs']], use_container_width=True)
                    
                    # --- ÁREA DE EDIÇÃO DO HISTÓRICO ---
                    st.divider()
                    st.subheader("📝 Editar Histórico")
                    
                    # Selectbox para escolher qual linha editar
                    # Cria lista de opções legíveis: "Setor (Data)"
                    opcoes_trams = {f"{t[2]} ({pd.to_datetime(t[3]).strftime('%d/%m/%Y')})": t[0] for t in trams_data}
                    sel_t_label = st.selectbox("Selecione a movimentação para corrigir:", ["Selecione..."] + list(opcoes_trams.keys()))
                    
                    if sel_t_label != "Selecione...":
                        tid_edit = opcoes_trams[sel_t_label]
                        # Pega os dados da linha selecionada
                        row_edit = next((t for t in trams_data if t[0] == tid_edit), None)
                        
                        if row_edit:
                            with st.form(f"form_edit_tram_{tid_edit}"):
                                col_e1, col_e2 = st.columns(2)
                                
                                # Campos de Edição
                                idx_setor = setores_tramitacao.index(row_edit[2]) if row_edit[2] in setores_tramitacao else 0
                                e_setor = col_e1.selectbox("Setor", setores_tramitacao, index=idx_setor)
                                
                                e_dt_ent_val = datetime.strptime(row_edit[3], '%Y-%m-%d').date() if row_edit[3] else date.today()
                                e_dt_ent = col_e1.date_input("Data Entrada", value=e_dt_ent_val)
                                
                                # Lógica para Data de Saída (pode ser nula)
                                has_exit_date = col_e2.checkbox("Possui data de saída fechada?", value=bool(row_edit[4]))
                                e_dt_sai = None
                                if has_exit_date:
                                    e_dt_sai_val = datetime.strptime(row_edit[4], '%Y-%m-%d').date() if row_edit[4] else date.today()
                                    e_dt_sai = col_e2.date_input("Data Saída", value=e_dt_sai_val)
                                
                                e_obs = st.text_area("Observação", value=row_edit[5] if row_edit[5] else "")
                                
                                c_btn1, c_btn2 = st.columns(2)
                                if c_btn1.form_submit_button("💾 Salvar Correção", type="primary"):
                                    saida_db = e_dt_sai.strftime('%Y-%m-%d') if has_exit_date and e_dt_sai else None
                                    executar_query("UPDATE tramitacao SET setor=?, data_entrada=?, data_saida=?, observacao=? WHERE id=?",
                                                 (e_setor, e_dt_ent.strftime('%Y-%m-%d'), saida_db, e_obs, tid_edit), commit=True)
                                    st.success("Movimentação atualizada!")
                                    st.rerun()
                                    
                                if c_btn2.form_submit_button("🗑️ Excluir Movimentação", type="danger"):
                                    executar_query("DELETE FROM tramitacao WHERE id=?", (tid_edit,), commit=True)
                                    st.success("Movimentação removida!")
                                    st.rerun()

                else:
                    st.info("Sem histórico para exibir ou editar.")

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
            st.warning("Insira API Key.")
        elif procs:
            sel_ia_key = st.selectbox("Processo:", list(opcoes.keys()), key="sel_ia")
            pid_ia = opcoes[sel_ia_key]
            d_ia = buscar_processo(pid_ia)
            upload_proj = st.file_uploader("PDF Projeto", type='pdf')
            upload_lei = st.file_uploader("PDF Lei", type='pdf')
            
            if st.button("Analisar") and upload_proj and upload_lei:
                with st.spinner("Analisando..."):
                    try:
                        txt_p = PyPDF2.PdfReader(upload_proj).pages[0].extract_text()
                        txt_l = PyPDF2.PdfReader(upload_lei).pages[0].extract_text()
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        res = model.generate_content(f"Analise projeto {d_ia[1]} vs Lei.\nLei: {txt_l[:2000]}\nProj: {txt_p[:2000]}")
                        st.markdown(res.text)
                    except Exception as e: st.error(f"Erro: {e}")

    # ABA 6: DASHBOARD
    with tab6:
        st.header("📈 Dashboard Gerencial")
        if pd is None or px is None:
            st.error("Bibliotecas gráficas não disponíveis.")
        else:
            df_dash = get_processos_df()
            if not df_dash.empty:
                # KPIs
                c1, c2, c3, c4 = st.columns(4)
                total = len(df_dash)
                area = df_dash['area'].sum()
                aprov = len(df_dash[df_dash['status'] == 'Aprovado'])
                dias = (pd.Timestamp.now() - df_dash['data_protocolo']).dt.days.mean()
                
                c1.metric("Total", total)
                c2.metric("Área Total", f"{area:,.2f}")
                c3.metric("Aprovados", aprov)
                c4.metric("Média Dias", f"{dias:.0f}")
                
                st.markdown("---")
                # Gráficos
                g1, g2 = st.columns(2)
                with g1:
                    fig = px.pie(df_dash['status'].value_counts().reset_index(), values='count', names='status', title='Status')
                    st.plotly_chart(fig, use_container_width=True)
                with g2:
                    fig = px.bar(df_dash['uso'].value_counts().reset_index(), x='count', y='uso', orientation='h', title='Uso')
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Cadastre processos para ver os indicadores.")

if __name__ == "__main__":
    main()

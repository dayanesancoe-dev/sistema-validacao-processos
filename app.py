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
        
        # === CORREÇÃO DE NOMES DE SETORES ANTIGOS ===
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
                # Busca usuário nos Secrets ou usa admin/admin como fallback
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
    
    # Campo para API Key (Opcional se já estiver no secrets)
    api_key_input = st.sidebar.text_input("API Key Gemini", type="password")
    if api_key_input: 
        genai.configure(api_key=api_key_input)
    
    # === DIAGNÓSTICO RÁPIDO ===
    if genai.__version__ < "0.8.3":
        st.sidebar.error(f"⚠️ Versão IA antiga: {genai.__version__}. Atualize o requirements.txt")

    # === SEÇÃO DE DADOS E BACKUP ===
    st.sidebar.markdown("---")
    st.sidebar.header("💾 Dados e Backup")
    
    if conn and pd is not None:
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

        if os.path.exists("processos.db"):
            with open("processos.db", "rb") as f:
                st.sidebar.download_button(
                    label="📦 Baixar Backup (.db)",
                    data=f,
                    file_name=f"backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db",
                    mime="application/octet-stream"
                )
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("⚠️ Restaurar Backup")
        uploaded_db = st.sidebar.file_uploader("Upload do arquivo .db", type="db")
        if uploaded_db:
            st.sidebar.warning("Isso substituirá TODOS os dados.")
            if st.sidebar.button("🔴 Confirmar Restauração"):
                try:
                    with open("processos.db", "wb") as f:
                        f.write(uploaded_db.getbuffer())
                    st.toast("Restaurado com sucesso! Reiniciando...", icon="✅")
                    import time
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Erro: {e}")

    # --- ABAS ---
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["➕ Novo", "📝 Gerenciar", "🔄 Tramitação", "📊 Kanban", "🤖 IA", "📈 Dashboard"])

    # === LISTAS GLOBAIS (ATUALIZADAS) ===
    usos = [
        "Multifamiliar", 
        "Serviços", 
        "Comércio Varejista", 
        "Indústria", 
        "Unifamiliar", 
        "Misto", 
        "Sem destinação específica"
    ]
    
    tipos = ["Aprovação Inicial", "Regularização", "Modificação", "Habite-se"]
    
    # Sintaxe corrigida (fechamento do colchete)
    setores = ["Análise prévia", "Pré-análise", "Analista", "Parecer externo", "Fiscalização", "Emissão de documentos", "Requerente"]

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
            tipo = c2.selectbox("Tipo", tipos)
            data = c2.date_input("Data Protocolo")
            
            if st.form_submit_button("Salvar Processo"):
                suc, msg = executar_query(
                    'INSERT INTO processos (numero, rt, requerente, analista, uso, tipologia, area, data_protocolo) VALUES (?,?,?,?,?,?,?,?)',
                    (num, rt, req, ana, uso, tipo, area, data.strftime('%Y-%m-%d')), commit=True
                )
                if suc: st.success("Sucesso!"); st.rerun()
                else: st.error(f"Erro: {msg}")

    # --- ABA 2: GERENCIAR ---
    with tab2:
        st.header("Editar ou Excluir")
        procs = listar_processos()
        if procs:
            opcoes = {f"{p[1]} - {p[3]}": p[0] for p in procs}
            sel = st.selectbox("Selecione:", list(opcoes.keys()))
            pid = opcoes[sel]
            d = buscar_processo(pid)
            
            if d:
                st.markdown("---")
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
                    
                    st.markdown("---")
                    btn_save = st.form_submit_button("💾 Salvar Alterações", type="primary")
                    btn_del = st.form_submit_button("🗑️ Deletar Processo", type="secondary")

                    if btn_save:
                        executar_query('UPDATE processos SET numero=?, rt=?, requerente=?, analista=?, uso=?, tipologia=?, area=?, data_protocolo=? WHERE id=?',
                                     (enum, ert, ereq, eana, euso, etipo, earea, edata.strftime('%Y-%m-%d'), pid), commit=True)
                        st.success("Salvo!"); st.rerun()
                    
                    if btn_del:
                        st.session_state[f'del_{pid}'] = True

                if st.session_state.get(f'del_{pid}'):
                    st.warning("Confirma a exclusão?")
                    if st.button("Sim, Excluir Definitivamente"):
                        executar_query('DELETE FROM tramitacao WHERE processo_id=?', (pid,), commit=True)
                        executar_query('DELETE FROM analises WHERE processo_id=?', (pid,), commit=True)
                        executar_query('DELETE FROM processos WHERE id=?', (pid,), commit=True)
                        st.success("Excluído!"); st.rerun()

    # --- ABA 3: TRAMITAÇÃO ---
    with tab3:
        st.header("Tramitação")
        if procs:
            sel_key = st.selectbox("Processo:", list(opcoes.keys()), key="tram_sel")
            pid_tram = opcoes[sel_key]
            
            with st.form("new_tram"):
                st.subheader("Nova Movimentação")
                c1, c2 = st.columns(2)
                setor = c1.selectbox("Setor Destino", setores)
                obs = c2.text_area("Observação", height=68)
                st.markdown("**Datas:**")
                c3, c4 = st.columns(2)
                with c3:
                    dt_ent = st.date_input("📅 Data de Entrada", value=date.today())
                with c4:
                    tem_saida = st.checkbox("Informar Data de Saída?")
                    if tem_saida:
                        dt_sai = st.date_input("📅 Data de Saída", value=date.today())
                    else:
                        dt_sai = None
                        st.caption("Saída 'Em Aberto' (Atual)")
                
                st.markdown("---")
                if st.form_submit_button("Movimentar", type="primary"):
                    if not tem_saida:
                        executar_query("UPDATE tramitacao SET data_saida=? WHERE processo_id=? AND data_saida IS NULL", 
                                     (dt_ent.strftime('%Y-%m-%d'), pid_tram), commit=True)
                    saida_val = dt_sai.strftime('%Y-%m-%d') if tem_saida and dt_sai else None
                    executar_query("INSERT INTO tramitacao (processo_id, setor, data_entrada, data_saida, observacao) VALUES (?,?,?,?,?)",
                                 (pid_tram, setor, dt_ent.strftime('%Y-%m-%d'), saida_val, obs), commit=True)
                    st.success("Movimentação registrada!")
                    st.rerun()

            st.divider()
            # Busca do banco em qualquer ordem, pois ordenamos no Pandas
            suc, res = executar_query("SELECT * FROM tramitacao WHERE processo_id=?", (pid_tram,))
            if suc:
                rows = res.fetchall()
                if rows:
                    df = pd.DataFrame(rows, columns=['ID', 'PID', 'Setor', 'Entrada', 'Saída', 'Obs'])
                    df['Setor'] = df['Setor'].replace({'Pró-análise': 'Pré-análise', 'Pró-Análise': 'Pré-análise', 'Pro-analise': 'Pré-análise'})
                    df['Entrada'] = pd.to_datetime(df['Entrada'])
                    df['Saída'] = pd.to_datetime(df['Saída'])
                    now = pd.Timestamp.now().normalize()
                    df['Dias'] = df.apply(lambda x: ((x['Saída'] if pd.notnull(x['Saída']) else now) - x['Entrada']).days, axis=1)
                    
                    st.subheader("📊 Total de Dias por Setor")
                    df_resumo = df.groupby('Setor')['Dias'].sum().reset_index().sort_values('Dias', ascending=False)
                    st.dataframe(df_resumo, use_container_width=True)
                    
                    st.subheader("📜 Histórico Detalhado")
                    # === ORDENAÇÃO CRONOLÓGICA (Antigo -> Novo) ===
                    df_show = df.sort_values(by='Entrada', ascending=True).copy()
                    
                    df_show['Entrada'] = df_show['Entrada'].dt.strftime('%d/%m/%Y')
                    df_show['Saída'] = df_show['Saída'].dt.strftime('%d/%m/%Y').fillna("Atual")
                    st.dataframe(df_show[['Setor', 'Entrada', 'Saída', 'Dias', 'Obs']], use_container_width=True)
                    
                    st.divider()
                    st.subheader("📝 Editar Histórico")
                    # Menu de seleção para edição
                    opts_t = {f"{r[2]} ({pd.to_datetime(r[3]).strftime('%d/%m/%Y')})": r[0] for r in rows}
                    sel_t = st.selectbox("Selecione para corrigir:", ["Selecione..."] + list(opts_t.keys()))
                    if sel_t != "Selecione...":
                        tid = opts_t[sel_t]
                        r = next((x for x in rows if x[0] == tid), None)
                        if r:
                            with st.form(f"edit_tram_{tid}"):
                                ec1, ec2 = st.columns(2)
                                cur_sector = r[2]
                                if cur_sector in ['Pró-análise', 'Pró-Análise']: cur_sector = 'Pré-análise'
                                idx_setor = setores.index(cur_sector) if cur_sector in setores else 0
                                esetor = ec1.selectbox("Setor", setores, index=idx_setor)
                                eobs = ec2.text_input("Observação", r[5] or "")
                                st.markdown("**Datas:**")
                                ec3, ec4 = st.columns(2)
                                with ec3:
                                    edtent = st.date_input("Data Entrada", datetime.strptime(r[3], '%Y-%m-%d').date())
                                with ec4:
                                    has_exit = st.checkbox("Possui Saída?", value=bool(r[4]))
                                    edtsai = None
                                    if has_exit:
                                        val_sai = datetime.strptime(r[4], '%Y-%m-%d').date() if r[4] else date.today()
                                        edtsai = st.date_input("Data Saída", val_sai)
                                st.markdown("---")
                                btn_t_save = st.form_submit_button("Salvar Correção", type="primary")
                                btn_t_del = st.form_submit_button("Excluir Movimentação")
                                if btn_t_save:
                                    s_val = edtsai.strftime('%Y-%m-%d') if has_exit and edtsai else None
                                    executar_query("UPDATE tramitacao SET setor=?, data_entrada=?, data_saida=?, observacao=? WHERE id=?",
                                                 (esetor, edtent.strftime('%Y-%m-%d'), s_val, eobs, tid), commit=True)
                                    st.success("Atualizado!")
                                    st.rerun()
                                if btn_t_del:
                                    executar_query("DELETE FROM tramitacao WHERE id=?", (tid,), commit=True)
                                    st.success("Apagado!")
                                    st.rerun()

    # --- ABA 4: KANBAN ---
    with tab4:
        st.header("Kanban")
        cols = st.columns(5)
        stats = ['Protocolado', 'Em Análise', 'Aguardando Correções', 'Aprovado', 'Reprovado']
        for i, s in enumerate(stats):
            with cols[i]:
                st.caption(f"**{s}**")
                for p in [x for x in procs if x[9] == s]:
                    with st.container(border=True):
                        st.write(f"**{p[1]}**\n{p[3]}")
                        col_back, col_next = st.columns(2)
                        if i > 0:
                            if col_back.button("⬅️", key=f"back_{p[0]}"):
                                executar_query("UPDATE processos SET status=? WHERE id=?", (stats[i-1], p[0]), commit=True)
                                st.rerun()
                        if i < 4:
                            if col_next.button("➡️", key=f"next_{p[0]}"):
                                executar_query("UPDATE processos SET status=? WHERE id=?", (stats[i+1], p[0]), commit=True)
                                st.rerun()

    # --- ABA 5: IA ---
    with tab5:
        st.header("Análise IA")
        if not api_key_input and "GOOGLE_API_KEY" not in os.environ:
             st.info("Insira a API Key no menu lateral para usar a IA.")
        elif procs:
            pid_ia = opcoes[st.selectbox("Processo:", list(opcoes.keys()), key="ia_sel")]
            d_ia = buscar_processo(pid_ia)
            up_p = st.file_uploader("Projeto (PDF)", type='pdf', accept_multiple_files=True)
            up_l = st.file_uploader("Lei (PDF)", type='pdf', accept_multiple_files=True)
            if st.button("Analisar") and up_p and up_l:
                with st.spinner("Analisando..."):
                    try:
                        txt_p = ""
                        for p_file in up_p:
                            reader = PyPDF2.PdfReader(p_file)
                            for page in reader.pages: txt_p += page.extract_text() or ""
                        txt_l = ""
                        for l_file in up_l:
                            reader = PyPDF2.PdfReader(l_file)
                            for page in reader.pages: txt_l += page.extract_text() or ""
                        
                        # Modelos atualizados
                        modelos = ['models/gemini-2.0-flash', 'models/gemini-1.5-flash', 'models/gemini-1.5-pro']
                        resultado, modelo_usado, erros = None, "", []
                        
                        for m_nome in modelos:
                            try:
                                model = genai.GenerativeModel(m_nome)
                                resultado = model.generate_content(f"""
                                Você é um analista experiente. Analise se o projeto cumpre a legislação.
                                DADOS: {d_ia[3]}, {d_ia[5]}, {d_ia[7]}m²
                                LEI: {txt_l[:30000]}
                                PROJETO: {txt_p[:30000]}
                                Responda com: 1. Resumo, 2. Conformidade, 3. Desacordo, 4. Conclusão.
                                """)
                                modelo_usado = m_nome
                                break
                            except Exception as e:
                                erros.append(f"{m_nome}: {str(e)}")
                                continue
                        
                        if resultado:
                            st.success(f"Análise realizada! (Modelo: {modelo_usado})")
                            st.markdown(resultado.text)
                        else:
                            st.error("Erro ao analisar. Detalhes:")
                            for erro in erros: st.write(erro)
                                
                    except Exception as e: st.error(f"Erro geral: {e}")

    # --- ABA 6: DASHBOARD ---
    with tab6:
        st.header("Dashboard")
        if pd is not None and px is not None:
            df = get_processos_df()
            if not df.empty:
                # Métricas
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total", len(df))
                c2.metric("Área Total", f"{df['area'].sum():,.0f} m²")
                c3.metric("Aprovados", len(df[df['status']=='Aprovado']))
                dias = (pd.Timestamp.now() - df['data_protocolo']).dt.days.mean()
                c4.metric("Média Dias", f"{dias:.0f}")
                st.divider()
                
                # Layout Grade
                row1_1, row1_2 = st.columns(2)
                row2_1, row2_2 = st.columns(2)
                
                with row1_1:
                    st.subheader("Status")
                    st.plotly_chart(px.pie(df, names='status', title='Status'), use_container_width=True)
                
                with row1_2:
                    st.subheader("Uso")
                    count_uso = df['uso'].value_counts().reset_index()
                    count_uso.columns = ['uso', 'count']
                    st.plotly_chart(px.bar(count_uso, x='count', y='uso', orientation='h', title='Uso'), use_container_width=True)
                
                with row2_1:
                    st.subheader("Tipologia")
                    count_tipo = df['tipologia'].value_counts().reset_index()
                    count_tipo.columns = ['tipologia', 'count']
                    st.plotly_chart(px.bar(count_tipo, x='count', y='tipologia', orientation='h', title='Tipologia'), use_container_width=True)
                
                with row2_2:
                    st.subheader("% Tempo por Setor")
                    try:
                        df_tram_all = pd.read_sql_query("SELECT * FROM tramitacao", conn)
                        if not df_tram_all.empty:
                            df_tram_all['data_entrada'] = pd.to_datetime(df_tram_all['data_entrada'])
                            df_tram_all['data_saida'] = pd.to_datetime(df_tram_all['data_saida'])
                            now = pd.Timestamp.now().normalize()
                            df_tram_all['data_saida'] = df_tram_all['data_saida'].fillna(now)
                            df_tram_all['dias'] = (df_tram_all['data_saida'] - df_tram_all['data_entrada']).dt.days
                            df_tram_all['setor'] = df_tram_all['setor'].replace({'Pró-análise': 'Pré-análise', 'Pró-Análise': 'Pré-análise'})
                            df_setor_total = df_tram_all.groupby('setor')['dias'].sum().reset_index()
                            st.plotly_chart(px.pie(df_setor_total, values='dias', names='setor', title='Tempo Total (Dias)'), use_container_width=True)
                    except: pass

                # === SEÇÃO: PRODUTIVIDADE POR ANALISTA ===
                st.divider()
                st.subheader("Produtividade da Equipe")
                
                df_analista = df[df['analista'].str.len() > 0].groupby('analista')['area'].sum().reset_index()
                df_analista = df_analista.sort_values('area', ascending=True)
                
                if not df_analista.empty:
                    fig_analista = px.bar(
                        df_analista, 
                        x='area', 
                        y='analista', 
                        orientation='h',
                        title='Total de m² Analisados por Analista',
                        text_auto='.0f',
                        labels={'area': 'Área Total (m²)', 'analista': 'Analista'}
                    )
                    st.plotly_chart(fig_analista, use_container_width=True)
                else:
                    st.info("Nenhum analista atribuído aos processos ainda.")

if __name__ == "__main__":
    main()

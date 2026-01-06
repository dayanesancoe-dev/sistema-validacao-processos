import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import io
import re

# Tentar importar bibliotecas
try:
    import PyPDF2
    PDF_DISPONIVEL = True
except ImportError:
    PDF_DISPONIVEL = False
    st.warning("⚠️ PyPDF2 não instalado. Instale com: pip install PyPDF2")

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    REPORTLAB_DISPONIVEL = True
except ImportError:
    REPORTLAB_DISPONIVEL = False
    st.warning("⚠️ ReportLab não instalado. Instale com: pip install reportlab")

try:
    import google.generativeai as genai
    GEMINI_DISPONIVEL = True
except ImportError:
    GEMINI_DISPONIVEL = False
    st.warning("⚠️ Google Generative AI não instalado. Instale com: pip install google-generativeai")

# Configuração da página
st.set_page_config(
    page_title="Sistema de Validação de Processos",
    page_icon="🏛️",
    layout="wide"
)

st.title("🏛️ Sistema de Validação de Processos com IA")
st.markdown("**Prefeitura de Contagem** — Análise Inteligente com Google Gemini Pro")

# ==================== CONFIGURAÇÃO GEMINI ====================

# Inicializar session_state para API key
if 'gemini_api_key' not in st.session_state:
    st.session_state.gemini_api_key = ""

# Sidebar para configuração da API
with st.sidebar:
    st.header("⚙️ Configurações")
    st.write("**Google Gemini Pro**")

    api_key_input = st.text_input(
        "API Key do Gemini",
        type="password",
        value=st.session_state.gemini_api_key,
        help="Cole sua API Key do Google AI Studio",
        key="api_key_sidebar"
    )

    if api_key_input != st.session_state.gemini_api_key:
        st.session_state.gemini_api_key = api_key_input
        if api_key_input and GEMINI_DISPONIVEL:
            try:
                genai.configure(api_key=api_key_input)
                st.success("✅ API configurada!")
            except Exception as e:
                st.error(f"❌ Erro na API: {str(e)}")

    if not st.session_state.gemini_api_key:
        st.info("📌 Para análise inteligente, configure sua API Key do Gemini")
        st.markdown("[🔗 Obter API Key](https://makersuite.google.com/app/apikey)")

    st.divider()
    st.write("**Status do Sistema:**")
    st.write(f"{'✅' if PDF_DISPONIVEL else '❌'} PyPDF2")
    st.write(f"{'✅' if REPORTLAB_DISPONIVEL else '❌'} ReportLab")
    st.write(f"{'✅' if GEMINI_DISPONIVEL else '❌'} Gemini AI")
    st.write(f"{'✅' if st.session_state.gemini_api_key else '❌'} API Key")

# Inicializar banco de dados
@st.cache_resource
def init_db():
    conn = sqlite3.connect('processos.db', check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_processo TEXT UNIQUE NOT NULL,
            requerente TEXT NOT NULL,
            rt TEXT NOT NULL,
            analista TEXT NOT NULL,
            uso TEXT NOT NULL,
            area_total REAL NOT NULL,
            estatus TEXT DEFAULT 'Em análise',
            data_protocolo TEXT DEFAULT CURRENT_TIMESTAMP,
            data_cadastro TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS legislacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            descricao TEXT,
            data_criacao TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS regras_legislacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            legislacao_id INTEGER NOT NULL,
            artigo TEXT NOT NULL,
            descricao TEXT NOT NULL,
            campo_validacao TEXT NOT NULL,
            operador TEXT NOT NULL,
            valor_referencia REAL NOT NULL,
            mensagem_erro TEXT,
            FOREIGN KEY (legislacao_id) REFERENCES legislacoes(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pdfs_legislacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            legislacao_id INTEGER NOT NULL,
            pdf_nome TEXT NOT NULL,
            pdf_conteudo BLOB NOT NULL,
            data_upload TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (legislacao_id) REFERENCES legislacoes(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pdfs_projeto (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_id INTEGER NOT NULL,
            pdf_nome TEXT NOT NULL,
            pdf_conteudo BLOB NOT NULL,
            tipo_documento TEXT,
            data_upload TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (processo_id) REFERENCES processos(id)
        )
    ''')

    conn.commit()
    return conn, cursor

conn, cursor = init_db()

# ==================== FUNÇÕES DE ANÁLISE COM IA ====================

def extrair_texto_pdf(pdf_bytes):
    """Extrai texto de um PDF"""
    if not PDF_DISPONIVEL:
        return "[PyPDF2 não instalado]"

    try:
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        texto = ""
        for page in pdf_reader.pages:
            texto += page.extract_text() + "\n"
        return texto
    except Exception as e:
        return f"[Erro ao extrair: {str(e)}]"

def analisar_com_gemini(texto_projeto, texto_legislacao, regras):
    """Usa o Gemini Pro para análise detalhada"""
    if not GEMINI_DISPONIVEL or not st.session_state.gemini_api_key:
        return None

    try:
        genai.configure(api_key=st.session_state.gemini_api_key)
        model = genai.GenerativeModel('gemini-pro')

        # Montar o prompt detalhado
        regras_texto = "\n".join([f"- {r[1]}: {r[2]}" for r in regras])

        prompt = f"""Você é um analista técnico de projetos arquitetônicos da Prefeitura de Contagem.

LEGISLAÇÃO APLICÁVEL:
{texto_legislacao[:3000]}

REGRAS ESPECÍFICAS A VERIFICAR:
{regras_texto}

PROJETO ARQUITETÔNICO SUBMETIDO:
{texto_projeto[:5000]}

INSTRUÇÕES:
Analise o projeto comparando com a legislação e as regras específicas. Para cada regra, identifique:

1. CONFORMIDADES: O que está de acordo
2. NÃO CONFORMIDADES: O que viola a legislação (cite o artigo específico)
3. PONTOS DE ATENÇÃO: O que precisa ser verificado com mais detalhe
4. RECOMENDAÇÕES: Sugestões de correção

Seja OBJETIVO, TÉCNICO e SEMPRE CITE OS ARTIGOS DA LEI.

Formato da resposta:
## CONFORMIDADES
- [lista]

## NÃO CONFORMIDADES
- [Artigo X] Descrição do problema
- [lista]

## PONTOS DE ATENÇÃO
- [lista]

## RECOMENDAÇÕES
- [lista]

## CONCLUSÃO
[Aprovado/Reprovado com justificativa]
"""

        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        st.error(f"❌ Erro na análise com IA: {str(e)}")
        return None

def gerar_relatorio_pdf_com_ia(resultado, analise_ia):
    """Gera relatório PDF com análise da IA"""
    if not REPORTLAB_DISPONIVEL:
        return None

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    story = []
    styles = getSampleStyleSheet()

    titulo_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=30,
        alignment=TA_CENTER
    )

    subtitulo_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2d5aa6'),
        spaceAfter=12
    )

    # Cabeçalho
    story.append(Paragraph("RELATÓRIO DE ANÁLISE TÉCNICA COM IA", titulo_style))
    story.append(Paragraph("Prefeitura de Contagem - Análise Assistida por Inteligência Artificial", styles['Normal']))
    story.append(Spacer(1, 0.5*cm))

    # Dados do processo
    story.append(Paragraph("DADOS DO PROCESSO", subtitulo_style))

    dados = [
        ['Número:', resultado['numero_processo']],
        ['Requerente:', resultado['requerente']],
        ['Data:', datetime.now().strftime('%d/%m/%Y %H:%M')],
        ['Status:', 'APROVADO' if resultado['total_violacoes'] == 0 else 'REPROVADO']
    ]

    tabela = Table(dados, colWidths=[5*cm, 10*cm])
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f0fe')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(tabela)
    story.append(Spacer(1, 1*cm))

    # Resumo
    story.append(Paragraph("RESUMO DA VALIDAÇÃO", subtitulo_style))

    resumo = [
        ['Regras Analisadas', str(resultado['total_regras'])],
        ['Conformidades', str(resultado['total_conformidades'])],
        ['Violações', str(resultado['total_violacoes'])]
    ]

    tab_resumo = Table(resumo, colWidths=[8*cm, 7*cm])
    cor = colors.HexColor('#34a853') if resultado['total_violacoes'] == 0 else colors.HexColor('#ea4335')
    tab_resumo.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), cor),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.white),
    ]))
    story.append(tab_resumo)
    story.append(Spacer(1, 1*cm))

    # Análise da IA
    if analise_ia:
        story.append(PageBreak())
        story.append(Paragraph("ANÁLISE TÉCNICA DETALHADA (IA)", subtitulo_style))
        story.append(Spacer(1, 0.3*cm))

        # Dividir análise em parágrafos
        paragrafos = analise_ia.split('\n')
        for para in paragrafos:
            if para.strip():
                story.append(Paragraph(para, styles['Normal']))
                story.append(Spacer(1, 0.2*cm))

    # Violações encontradas
    if resultado['violacoes']:
        story.append(PageBreak())
        story.append(Paragraph("PONTOS A CORRIGIR", subtitulo_style))

        for i, v in enumerate(resultado['violacoes'], 1):
            texto = f"<b>{i}. {v['artigo']}</b><br/>{v['descricao']}<br/><b>Problema:</b> {v['mensagem']}<br/><b>Esperado:</b> {v['valor_esperado']} | <b>Encontrado:</b> {v['valor_encontrado']}"
            story.append(Paragraph(texto, styles['Normal']))
            story.append(Spacer(1, 0.5*cm))

    # Rodapé
    story.append(Spacer(1, 2*cm))
    story.append(Paragraph("_" * 80, styles['Normal']))
    story.append(Paragraph(f"Relatório gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}<br/>Análise assistida por Google Gemini Pro", styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    return buffer

# ==================== FUNÇÕES DO BANCO ====================

def cadastrar_processo(numero, requerente, rt, analista, uso, area):
    try:
        cursor.execute('INSERT INTO processos (numero_processo, requerente, rt, analista, uso, area_total) VALUES (?, ?, ?, ?, ?, ?)', 
                      (numero, requerente, rt, analista, uso, area))
        conn.commit()
        st.success(f"✅ Processo {numero} cadastrado!")
        return True
    except sqlite3.IntegrityError:
        st.error(f"❌ Processo {numero} já existe!")
        return False

def deletar_processo(processo_id):
    try:
        cursor.execute('DELETE FROM pdfs_projeto WHERE processo_id = ?', (processo_id,))
        cursor.execute('DELETE FROM processos WHERE id = ?', (processo_id,))
        conn.commit()
        st.success("✅ Processo deletado!")
        return True
    except:
        return False

def listar_processos():
    cursor.execute('SELECT id, numero_processo, requerente, rt, uso, area_total, estatus FROM processos')
    return cursor.fetchall()

def cadastrar_legislacao(nome, descricao):
    try:
        cursor.execute('INSERT INTO legislacoes (nome, descricao) VALUES (?, ?)', (nome, descricao))
        conn.commit()
        st.success(f"✅ Legislação '{nome}' cadastrada!")
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        st.error(f"❌ Legislação '{nome}' já existe!")
        return None

def deletar_legislacao(legislacao_id):
    try:
        cursor.execute('DELETE FROM regras_legislacao WHERE legislacao_id = ?', (legislacao_id,))
        cursor.execute('DELETE FROM pdfs_legislacao WHERE legislacao_id = ?', (legislacao_id,))
        cursor.execute('DELETE FROM legislacoes WHERE id = ?', (legislacao_id,))
        conn.commit()
        st.success("✅ Legislação deletada!")
        return True
    except:
        return False

def listar_legislacoes():
    cursor.execute('SELECT id, nome, descricao FROM legislacoes')
    return cursor.fetchall()

def anexar_pdf_projeto(processo_id, pdf_file, tipo_doc):
    try:
        cursor.execute('INSERT INTO pdfs_projeto (processo_id, pdf_nome, pdf_conteudo, tipo_documento) VALUES (?, ?, ?, ?)', 
                      (processo_id, pdf_file.name, pdf_file.read(), tipo_doc))
        conn.commit()
        return True
    except:
        return False

def listar_pdfs_projeto(processo_id):
    cursor.execute('SELECT id, pdf_nome, tipo_documento FROM pdfs_projeto WHERE processo_id = ?', (processo_id,))
    return cursor.fetchall()

def obter_pdf_projeto_por_id(pdf_id):
    cursor.execute('SELECT pdf_nome, pdf_conteudo FROM pdfs_projeto WHERE id = ?', (pdf_id,))
    resultado = cursor.fetchone()
    return resultado if resultado else (None, None)

def obter_todos_pdfs_projeto(processo_id):
    cursor.execute('SELECT pdf_conteudo FROM pdfs_projeto WHERE processo_id = ?', (processo_id,))
    return cursor.fetchall()

def deletar_pdf_projeto(pdf_id):
    try:
        cursor.execute('DELETE FROM pdfs_projeto WHERE id = ?', (pdf_id,))
        conn.commit()
        return True
    except:
        return False

def obter_todos_pdfs_legislacao(legislacao_id):
    cursor.execute('SELECT pdf_conteudo FROM pdfs_legislacao WHERE legislacao_id = ?', (legislacao_id,))
    return cursor.fetchall()

def adicionar_regra(leg_id, artigo, descricao, campo, operador, valor, mensagem):
    try:
        cursor.execute('INSERT INTO regras_legislacao (legislacao_id, artigo, descricao, campo_validacao, operador, valor_referencia, mensagem_erro) VALUES (?, ?, ?, ?, ?, ?, ?)', 
                      (leg_id, artigo, descricao, campo, operador, valor, mensagem))
        conn.commit()
        st.success(f"✅ Regra adicionada!")
        return True
    except:
        return False

def listar_regras_legislacao(legislacao_id):
    cursor.execute('SELECT id, artigo, descricao, campo_validacao, operador, valor_referencia, mensagem_erro FROM regras_legislacao WHERE legislacao_id = ?', (legislacao_id,))
    return cursor.fetchall()

def deletar_regra(regra_id):
    try:
        cursor.execute('DELETE FROM regras_legislacao WHERE id = ?', (regra_id,))
        conn.commit()
        return True
    except:
        return False

def validar_processo(processo_id, legislacao_id, usar_ia=True):
    """Valida processo com análise de IA opcional"""
    cursor.execute('SELECT * FROM processos WHERE id = ?', (processo_id,))
    processo = cursor.fetchone()

    if not processo:
        return None

    cursor.execute('SELECT id, artigo, descricao, campo_validacao, operador, valor_referencia, mensagem_erro FROM regras_legislacao WHERE legislacao_id = ?', (legislacao_id,))
    regras = cursor.fetchall()

    conformidades = []
    violacoes = []

    campos_processo = {
        'numero_processo': processo[1],
        'requerente': processo[2],
        'rt': processo[3],
        'analista': processo[4],
        'uso': processo[5],
        'area_total': processo[6],
        'estatus': processo[7]
    }

    # Validação básica por regras
    for regra in regras:
        campo = regra[3]
        operador = regra[4]
        valor_ref = regra[5]

        if campo not in campos_processo:
            continue

        valor_campo = campos_processo[campo]
        resultado = False

        try:
            if operador == '>=':
                resultado = float(valor_campo) >= float(valor_ref)
            elif operador == '<=':
                resultado = float(valor_campo) <= float(valor_ref)
            elif operador == '>':
                resultado = float(valor_campo) > float(valor_ref)
            elif operador == '<':
                resultado = float(valor_campo) < float(valor_ref)
            elif operador == '==':
                resultado = str(valor_campo) == str(valor_ref)
            elif operador == '!=':
                resultado = str(valor_campo) != str(valor_ref)
        except:
            pass

        if resultado:
            conformidades.append({'artigo': regra[1], 'descricao': regra[2]})
        else:
            violacoes.append({
                'artigo': regra[1],
                'descricao': regra[2],
                'campo': campo,
                'valor_esperado': f"{operador} {valor_ref}",
                'valor_encontrado': valor_campo,
                'mensagem': regra[6]
            })

    # Extrair textos dos PDFs
    texto_projeto = ""
    pdfs_proj = obter_todos_pdfs_projeto(processo_id)
    for pdf in pdfs_proj:
        if pdf and pdf[0]:
            texto_projeto += extrair_texto_pdf(pdf[0]) + "\n\n"

    texto_legislacao = ""
    pdfs_leg = obter_todos_pdfs_legislacao(legislacao_id)
    for pdf in pdfs_leg:
        if pdf and pdf[0]:
            texto_legislacao += extrair_texto_pdf(pdf[0]) + "\n\n"

    # Análise com IA (se habilitada)
    analise_ia = None
    if usar_ia and texto_projeto and texto_legislacao:
        analise_ia = analisar_com_gemini(texto_projeto, texto_legislacao, regras)

    return {
        'numero_processo': processo[1],
        'requerente': processo[2],
        'total_regras': len(regras),
        'total_conformidades': len(conformidades),
        'total_violacoes': len(violacoes),
        'conformidades': conformidades,
        'violacoes': violacoes,
        'analise_ia': analise_ia
    }

# ==================== INTERFACE ====================

tab1, tab2, tab3 = st.tabs(["📝 Processos", "📚 Legislações", "🤖 Validar com IA"])

# ABA 1: PROCESSOS
with tab1:
    st.header("Gerenciar Processos")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("➕ Cadastrar")
        numero = st.text_input("Número", key="proc_num")
        requerente = st.text_input("Requerente", key="proc_req")
        rt = st.text_input("RT", key="proc_rt")
        analista = st.text_input("Analista", key="proc_ana")
        uso = st.selectbox("Uso", ["Residencial", "Comercial", "Industrial", "Misto"], key="proc_uso")
        area = st.number_input("Área (m²)", min_value=0.0, step=0.1, key="proc_area")

        if st.button("Cadastrar", key="proc_cad_btn"):
            if numero and requerente and rt and analista and area > 0:
                cadastrar_processo(numero, requerente, rt, analista, uso, area)
                st.rerun()

    with col2:
        st.subheader("📋 Lista")
        processos = listar_processos()
        if processos:
            for p in processos:
                with st.expander(f"{p[1]} - {p[2]}"):
                    st.write(f"RT: {p[3]} | Uso: {p[4]} | {p[5]}m²")
                    if st.button("🗑️", key=f"proc_del_{p[0]}"):
                        deletar_processo(p[0])
                        st.rerun()

# ABA 2: LEGISLAÇÕES
with tab2:
    st.header("Gerenciar Legislações")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("➕ Cadastrar")
        nome = st.text_input("Nome", key="leg_nome")
        desc = st.text_area("Descrição", key="leg_desc")

        if st.button("Cadastrar", key="leg_cad_btn"):
            if nome and desc:
                cadastrar_legislacao(nome, desc)
                st.rerun()

    with col2:
        st.subheader("📚 Lista")
        legs = listar_legislacoes()
        if legs:
            for l in legs:
                with st.expander(l[1]):
                    st.write(l[2])
                    if st.button("🗑️", key=f"leg_del_{l[0]}"):
                        deletar_legislacao(l[0])
                        st.rerun()

    st.divider()
    st.subheader("➕ Adicionar Regras")

    if legs:
        leg_sel = st.selectbox("Legislação", [f"ID {l[0]} - {l[1]}" for l in legs], key="regra_leg_sel")
        leg_id = int(leg_sel.split()[1])

        regras = listar_regras_legislacao(leg_id)
        if regras:
            for r in regras:
                col_r, col_d = st.columns([5, 1])
                col_r.write(f"📌 {r[1]}: {r[2]}")
                if col_d.button("🗑️", key=f"regra_del_{r[0]}"):
                    deletar_regra(r[0])
                    st.rerun()

        st.divider()
        col1, col2 = st.columns(2)

        with col1:
            art = st.text_input("Artigo", key="regra_art")
            desc_r = st.text_area("Descrição", key="regra_desc")
            campo = st.selectbox("Campo", ["area_total", "uso", "estatus"], key="regra_campo")

        with col2:
            op = st.selectbox("Operador", [">=", "<=", ">", "<", "==", "!="], key="regra_op")
            val = st.number_input("Valor", step=0.1, key="regra_val")
            msg = st.text_input("Mensagem", key="regra_msg")

        if st.button("Adicionar", key="regra_add_btn"):
            if art and desc_r and msg:
                adicionar_regra(leg_id, art, desc_r, campo, op, val, msg)
                st.rerun()

# ABA 3: VALIDAR COM IA
with tab3:
    st.header("🤖 Validação Inteligente com Gemini Pro")

    processos = listar_processos()
    legs = listar_legislacoes()

    if not st.session_state.gemini_api_key:
        st.warning("⚠️ Configure sua API Key do Gemini na barra lateral para usar análise com IA")

    if processos and legs:
        col1, col2 = st.columns(2)

        with col1:
            proc_sel = st.selectbox("Processo", [f"ID {p[0]} - {p[1]}" for p in processos], key="val_proc_sel")
            proc_id = int(proc_sel.split()[1])

        with col2:
            leg_sel = st.selectbox("Legislação", [f"ID {l[0]} - {l[1]}" for l in legs], key="val_leg_sel")
            leg_id = int(leg_sel.split()[1])

        st.divider()
        st.subheader("📎 PDFs do Projeto")

        pdfs = listar_pdfs_projeto(proc_id)
        if pdfs:
            for idx, pdf in enumerate(pdfs):
                col_a, col_b, col_c = st.columns([3, 1, 1])
                col_a.write(f"📄 {pdf[1]} ({pdf[2]})")

                pdf_nome, pdf_cont = obter_pdf_projeto_por_id(pdf[0])
                if pdf_cont:
                    col_b.download_button("⬇️", pdf_cont, pdf_nome, key=f"val_dl_{idx}")
                    if col_c.button("🗑️", key=f"val_del_{idx}"):
                        deletar_pdf_projeto(pdf[0])
                        st.rerun()

        novos = st.file_uploader("Anexar PDFs", type=['pdf'], accept_multiple_files=True, key="val_upload")
        tipo = st.selectbox("Tipo", ["Planta Baixa", "Corte", "Fachada", "Situação"], key="val_tipo")

        if novos and st.button("💾 Salvar", key="val_save_btn"):
            for pdf in novos:
                anexar_pdf_projeto(proc_id, pdf, tipo)
            st.success(f"✅ {len(novos)} PDF(s) anexado(s)!")
            st.rerun()

        st.divider()

        usar_ia = st.checkbox("🤖 Usar análise com IA Gemini Pro", value=True, key="usar_ia_check", 
                             disabled=not st.session_state.gemini_api_key)

        if st.button("🔍 VALIDAR PROJETO", key="val_btn", type="primary"):
            with st.spinner("🤖 Analisando projeto com IA..."):
                resultado = validar_processo(proc_id, leg_id, usar_ia)

            if resultado:
                st.divider()
                st.subheader(f"📋 Resultado - {resultado['numero_processo']}")

                col1, col2, col3 = st.columns(3)
                col1.metric("Regras", resultado['total_regras'])
                col2.metric("✅ Conformes", resultado['total_conformidades'])
                col3.metric("❌ Violações", resultado['total_violacoes'])

                if resultado['total_violacoes'] == 0:
                    st.success("🎉 APROVADO")
                else:
                    st.error(f"⚠️ REPROVADO")

                # Análise da IA
                if resultado.get('analise_ia'):
                    with st.expander("🤖 ANÁLISE DETALHADA DA IA", expanded=True):
                        st.markdown(resultado['analise_ia'])

                st.divider()

                # Gerar PDF
                pdf_rel = gerar_relatorio_pdf_com_ia(resultado, resultado.get('analise_ia'))
                if pdf_rel:
                    st.download_button(
                        "📥 BAIXAR RELATÓRIO COMPLETO",
                        pdf_rel,
                        f"relatorio_{resultado['numero_processo']}.pdf",
                        "application/pdf",
                        type="primary",
                        key="val_download_btn"
                    )

                if resultado['violacoes']:
                    with st.expander("❌ Violações Encontradas"):
                        for v in resultado['violacoes']:
                            st.error(f"**{v['artigo']}:** {v['descricao']}")
                            st.write(f"📌 {v['mensagem']}")
    else:
        st.warning("⚠️ Cadastre processos e legislações primeiro!")

st.divider()
st.markdown("---")
st.markdown("<div style='text-align: center'><p><strong>🏛️ Sistema de Validação com IA</strong></p><p>Prefeitura de Contagem • Powered by Google Gemini Pro</p></div>", unsafe_allow_html=True)

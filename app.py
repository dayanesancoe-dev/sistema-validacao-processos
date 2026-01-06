import streamlit as st
import io
from datetime import datetime

st.set_page_config(
    page_title="Sistema de Validação - Prefeitura Contagem",
    page_icon="🏛️",
    layout="wide"
)

st.title("🏛️ Sistema de Validação de Processos Arquitetônicos")
st.markdown("**Prefeitura de Contagem** — Análise Inteligente com Google Gemini AI")

# Configuração da API Key
st.sidebar.header("⚙️ Configurações")
st.sidebar.markdown("Configure sua **API Key do Google Gemini** para usar análise com IA:")

api_key = st.sidebar.text_input(
    "API Key:",
    type="password",
    help="Obtenha em: https://aistudio.google.com/app/apikey"
)

if api_key:
    st.sidebar.success("✅ API configurada!")
else:
    st.sidebar.warning("⚠️ Sem API Key")
    st.sidebar.markdown("[🔗 Obter API Key](https://aistudio.google.com/app/apikey)")

st.sidebar.divider()
st.sidebar.markdown("**Status:**")

# Verificar bibliotecas
try:
    import google.generativeai as genai
    st.sidebar.write("✅ Gemini AI")
    GEMINI_OK = True
except:
    st.sidebar.write("❌ Gemini AI")
    GEMINI_OK = False

try:
    import PyPDF2
    st.sidebar.write("✅ PyPDF2")
    PDF_OK = True
except:
    st.sidebar.write("❌ PyPDF2")
    PDF_OK = False

# Interface principal
st.divider()

# Abas
tab1, tab2 = st.tabs(["📋 Nova Análise", "❓ Ajuda"])

with tab1:
    if not api_key:
        st.warning("⚠️ Configure sua API Key na barra lateral para começar")
        st.info("**Como obter:** Acesse https://aistudio.google.com/app/apikey, faça login e crie uma chave")
        st.stop()

    if not GEMINI_OK or not PDF_OK:
        st.error("❌ Bibliotecas necessárias não instaladas")
        st.stop()

    # Configurar Gemini
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        st.error(f"❌ Erro na API Key: {str(e)}")
        st.stop()

    # Formulário
    st.header("📄 Upload dos Documentos")

    col_upload1, col_upload2 = st.columns(2)

    with col_upload1:
        st.subheader("📐 Projeto Arquitetônico")
        projetos_upload = st.file_uploader(
            "Anexe os PDFs do projeto (plantas, cortes, fachadas):",
            type=['pdf'],
            accept_multiple_files=True,
            key="upload_projetos"
        )
        if projetos_upload:
            st.success(f"✅ {len(projetos_upload)} arquivo(s) anexado(s)")

    with col_upload2:
        st.subheader("📜 Legislação Municipal")
        legislacoes_upload = st.file_uploader(
            "Anexe os PDFs da legislação aplicável:",
            type=['pdf'],
            accept_multiple_files=True,
            key="upload_legislacoes"
        )
        if legislacoes_upload:
            st.success(f"✅ {len(legislacoes_upload)} arquivo(s) anexado(s)")

    st.divider()
    st.header("📋 Dados do Processo")

    col_dados1, col_dados2, col_dados3 = st.columns(3)

    with col_dados1:
        numero_processo = st.text_input("Número do Processo:", placeholder="Ex: 2024.001.123")

    with col_dados2:
        nome_requerente = st.text_input("Nome do Requerente:", placeholder="Nome completo")

    with col_dados3:
        area_total = st.number_input("Área Total (m²):", min_value=0.0, step=0.1, format="%.2f")

    st.divider()
    st.subheader("📏 Regras a Verificar")

    regras_texto = st.text_area(
        "Digite as regras da legislação que devem ser verificadas (uma por linha):",
        placeholder="Exemplo:\nArt. 10 - Área mínima de lote: 50m²\nArt. 15 - Recuo frontal mínimo: 5m\nArt. 20 - Taxa de ocupação máxima: 60%\nArt. 25 - Altura máxima: 3 pavimentos",
        height=200,
        help="Liste os artigos da lei que devem ser verificados no projeto"
    )

    st.divider()

    # Botão de análise
    btn_analisar = st.button(
        "🔍 ANALISAR PROJETO COM IA",
        type="primary",
        use_container_width=True
    )

    if btn_analisar:
        # Validações
        if not projetos_upload:
            st.error("❌ Anexe ao menos 1 PDF do projeto!")
        elif not legislacoes_upload:
            st.error("❌ Anexe ao menos 1 PDF da legislação!")
        elif not numero_processo:
            st.error("❌ Informe o número do processo!")
        elif not nome_requerente:
            st.error("❌ Informe o nome do requerente!")
        elif not area_total or area_total <= 0:
            st.error("❌ Informe a área total!")
        elif not regras_texto:
            st.error("❌ Digite as regras a verificar!")
        else:
            with st.spinner("🤖 Analisando projeto com Inteligência Artificial... Aguarde..."):
                try:
                    # Extrair texto dos PDFs do projeto
                    texto_completo_projeto = ""
                    for idx, pdf_file in enumerate(projetos_upload, 1):
                        pdf_reader = PyPDF2.PdfReader(pdf_file)
                        for num_page, page in enumerate(pdf_reader.pages, 1):
                            texto_completo_projeto += f"\n[PROJETO - Arquivo {idx} - Página {num_page}]\n"
                            texto_completo_projeto += page.extract_text() + "\n"

                    # Extrair texto dos PDFs da legislação
                    texto_completo_legislacao = ""
                    for idx, pdf_file in enumerate(legislacoes_upload, 1):
                        pdf_reader = PyPDF2.PdfReader(pdf_file)
                        for num_page, page in enumerate(pdf_reader.pages, 1):
                            texto_completo_legislacao += f"\n[LEGISLAÇÃO - Arquivo {idx} - Página {num_page}]\n"
                            texto_completo_legislacao += page.extract_text() + "\n"

                    # Criar modelo Gemini
                    model = genai.GenerativeModel('gemini-pro')

                    # Prompt detalhado
                    prompt_analise = f"""Você é um ANALISTA TÉCNICO ESPECIALIZADO em projetos arquitetônicos da Prefeitura de Contagem - MG.

**DADOS DO PROCESSO:**
- Número do Processo: {numero_processo}
- Requerente: {nome_requerente}
- Área Total: {area_total}m²
- Data da Análise: {datetime.now().strftime('%d/%m/%Y às %H:%M')}

**LEGISLAÇÃO MUNICIPAL APLICÁVEL:**
{texto_completo_legislacao[:4500]}

**REGRAS ESPECÍFICAS A VERIFICAR:**
{regras_texto}

**PROJETO ARQUITETÔNICO SUBMETIDO:**
{texto_completo_projeto[:6500]}

**INSTRUÇÕES PARA ANÁLISE:**

Analise detalhadamente o projeto arquitetônico e verifique sua conformidade com a legislação municipal de Contagem.

**IMPORTANTE:**
- Cite SEMPRE o artigo específico da legislação
- Seja técnico, objetivo e preciso
- Identifique problemas com localização no projeto quando possível
- Use linguagem formal de parecer técnico

**FORMATO DA RESPOSTA:**

## ✅ CONFORMIDADES
Liste cada item que está em conformidade, citando:
- Artigo da lei
- Descrição do que está conforme
- Referência ao local do projeto onde foi verificado

## ❌ NÃO CONFORMIDADES - PONTOS A CORRIGIR
Para cada violação identificada, indique:
- **Artigo violado:** (número e texto da lei)
- **Problema encontrado:** (descrição detalhada)
- **Localização:** (onde no projeto está o problema)
- **Correção necessária:** (o que precisa ser alterado)

## ⚠️ PONTOS DE ATENÇÃO
Itens que necessitam:
- Verificação presencial
- Documentação complementar
- Esclarecimentos do responsável técnico

## 🔧 RECOMENDAÇÕES TÉCNICAS
Sugestões detalhadas para correção de cada não conformidade encontrada.

## 📊 PARECER TÉCNICO FINAL
Emita parecer conclusivo:
- **APROVADO** (se não houver nenhuma não conformidade)
- **REPROVADO** (se houver não conformidades)

Justifique tecnicamente sua conclusão citando os artigos relevantes.

---
**Análise técnica realizada em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}**
**Sistema de Validação com IA - Prefeitura de Contagem**
"""

                    # Gerar análise
                    resposta_gemini = model.generate_content(prompt_analise)

                    # Exibir resultado
                    st.divider()
                    st.header("📋 RELATÓRIO DE ANÁLISE TÉCNICA")

                    # Determinar status
                    texto_resposta = resposta_gemini.text.upper()
                    if "APROVADO" in texto_resposta and "REPROVADO" not in texto_resposta:
                        st.success("✅ PROJETO APROVADO")
                    elif "REPROVADO" in texto_resposta:
                        st.error("❌ PROJETO REPROVADO")
                    else:
                        st.warning("⚠️ ANÁLISE INCONCLUSIVA - Revisar manualmente")

                    st.divider()

                    # Exibir análise
                    st.markdown(resposta_gemini.text)

                    # Preparar relatório para download
                    relatorio_completo = f"""
================================================================================
PREFEITURA DE CONTAGEM - MG
RELATÓRIO DE ANÁLISE DE PROJETO ARQUITETÔNICO
================================================================================

PROCESSO: {numero_processo}
REQUERENTE: {nome_requerente}
ÁREA TOTAL: {area_total}m²
DATA DA ANÁLISE: {datetime.now().strftime('%d/%m/%Y às %H:%M')}

DOCUMENTOS ANALISADOS:
- Projeto: {len(projetos_upload)} arquivo(s) PDF
- Legislação: {len(legislacoes_upload)} arquivo(s) PDF

REGRAS VERIFICADAS:
{regras_texto}

================================================================================
ANÁLISE TÉCNICA
================================================================================

{resposta_gemini.text}

================================================================================
OBSERVAÇÕES:
- Análise realizada por Inteligência Artificial (Google Gemini Pro)
- Este relatório possui caráter orientativo
- A validação final deve ser confirmada por análise presencial
================================================================================

Sistema de Validação com IA
Prefeitura de Contagem - Setor de Liberação de Alvarás
Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}
"""

                    # Botão de download
                    st.divider()
                    st.download_button(
                        label="📥 BAIXAR RELATÓRIO COMPLETO (TXT)",
                        data=relatorio_completo,
                        file_name=f"relatorio_{numero_processo.replace('.', '_').replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain",
                        use_container_width=True,
                        type="primary"
                    )

                except Exception as erro_analise:
                    st.error(f"❌ Erro durante a análise: {str(erro_analise)}")
                    st.info("Verifique se sua API Key está correta e se os PDFs são válidos.")

with tab2:
    st.header("❓ Como Usar o Sistema")

    st.markdown("""
    ### 📝 Passo a Passo:

    1. **Configure a API Key** na barra lateral esquerda
       - Acesse: https://aistudio.google.com/app/apikey
       - Faça login e crie uma chave
       - Cole no campo da barra lateral

    2. **Anexe os PDFs do Projeto**
       - Plantas baixas
       - Cortes
       - Fachadas
       - Outros documentos técnicos

    3. **Anexe os PDFs da Legislação**
       - Lei de Uso e Ocupação do Solo
       - Código de Obras
       - Decretos municipais aplicáveis

    4. **Preencha os dados** do processo

    5. **Digite as regras** que devem ser verificadas

    6. **Clique em "Analisar"** e aguarde

    7. **Baixe o relatório** gerado

    ### 🔐 Segurança:
    - Sua API Key não é armazenada
    - Os PDFs são processados apenas durante a análise
    - Nenhum dado é salvo no servidor

    ### ⚠️ Importante:
    - A análise é orientativa
    - Validação final deve ser presencial
    - Sempre consulte a legislação atualizada
    """)

st.divider()
st.markdown("---")
st.markdown("""
<div style='text-align: center'>
    <p><strong>🏛️ Sistema de Validação com Inteligência Artificial</strong></p>
    <p>Prefeitura de Contagem - MG</p>
    <p style='font-size: 0.85em; color: #666;'>Powered by Google Gemini Pro • Desenvolvido com Streamlit</p>
</div>
""", unsafe_allow_html=True)

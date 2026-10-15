# JARVIS Bridge — pacote de implantação 1.0

## Estado real
Este pacote é código pronto para implantação, mas não está publicado nem ligado ao celular: isso depende de um host HTTPS, do webhook privado criado no MacroDroid e da autorização da conta Alexa/AWS. Não envie senhas ou URLs secretas no chat.

## Componentes
- API FastAPI autenticada por Bearer token.
- Lista de ações fechada: somente `open_whatsapp`.
- URL do webhook guardada em variável de ambiente do servidor.
- Proteção contra repetição por `request_id` usando SQLite.
- `openapi.yaml` para configurar uma GPT Action.
- Base de skill Alexa pt-BR em `alexa_skill/` (não publicar o handler demonstrativo sem validar assinatura/application ID).
- Testes automatizados básicos em `tests/`.

## Preparar MacroDroid no Galaxy
Crie uma macro chamada `JARVIS - Abrir WhatsApp`:
- Gatilho: webhook/HTTP trigger do MacroDroid, conforme a versão instalada.
- Ação: Aplicativos → Iniciar aplicativo → WhatsApp.
- Gere e copie a URL privada do webhook. Coloque-a apenas no segredo `MACRODROID_OPEN_WHATSAPP_URL` do servidor; nunca na especificação OpenAPI, instruções do GPT ou repositório.
- Confirme que o Android permite que o MacroDroid funcione em segundo plano e não está sendo encerrado pela otimização de bateria.

## Variáveis do servidor
Configure no host:
- `JARVIS_API_KEY`: segredo aleatório longo (32 bytes ou mais), diferente de qualquer senha pessoal.
- `MACRODROID_OPEN_WHATSAPP_URL`: URL privada do webhook acima.
- `JARVIS_IDEMPOTENCY_DB`: caminho persistente, por exemplo `/data/jarvis.sqlite3` (use volume persistente e uma única instância/worker; a deduplicação SQLite local não é compartilhada entre réplicas).
- `REQUEST_TIMEOUT_SECONDS=8`.

## Executar localmente
Python 3.11+:
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8000
```
Localhost não pode ser chamado pelo GPT na internet; para uma GPT Action, implante atrás de HTTPS. Não exponha o servidor sem token.

## Docker
O Dockerfile está incluído. Configure segredos por variáveis no host e monte volume persistente em `/data`. Não inclua `.env` no Git.

## GPT Action
1. Implante a API num host HTTPS e substitua o endereço em `openapi.yaml`.
2. No editor de GPT, adicione uma Action importando `openapi.yaml`.
3. Configure autenticação API Key/Bearer com o mesmo `JARVIS_API_KEY` do servidor.
4. Instrua o GPT a obter confirmação explícita antes de acionar qualquer ação real. Teste primeiro `/health`, depois `open_whatsapp`.

## Testes
```bash
pip install -r requirements.txt pytest
pytest -q
```

## Limitações e segurança
- Uma resposta HTTP bem-sucedida significa que o webhook respondeu, não prova visualmente que o WhatsApp abriu.
- Não aceita URLs arbitrárias, comandos de shell ou ações fora da lista permitida.
- A base Alexa é apenas demonstrativa até validar assinatura da Alexa e application ID com o SDK oficial.
- Para ações futuras (mensagens, chamadas, compras, exclusão de dados), exija confirmação específica; não as adicione à lista sem revisão.
- A ponte não consegue criar o webhook no seu aparelho, autenticar-se em contas externas ou publicar a skill sem a sua autorização.

## Implantação com Render (Blueprint incluído)
O arquivo `render.yaml` descreve um serviço Docker HTTPS com health check e disco persistente. Para a implantação automática, o código precisa estar em um repositório GitHub que você autorize o Render a acessar. O Render pedirá os dois segredos (`JARVIS_API_KEY` e `MACRODROID_OPEN_WHATSAPP_URL`) no painel; não os grave no repositório. O plano com disco persistente pode gerar cobrança.

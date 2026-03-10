## Plataforma de Anonimização de NF-e

Plataforma baseada em Docker para anonimizar dados sensíveis em arquivos XML de **Nota Fiscal Eletrônica (NF-e)** — o documento fiscal eletrônico padrão utilizado no Brasil para registrar transações comerciais.

A plataforma é composta por 3 containers:

- **presidio**: motor de anonimização de XML (Presidio + reconhecedores brasileiros customizados)
- **api**: gateway FastAPI para upload de múltiplos arquivos e orquestração do fluxo
- **ui**: interface web estática para visualização antes/depois e download dos arquivos anonimizados

### O que é NF-e?

NF-e (Nota Fiscal Eletrônica) é um documento fiscal digital emitido no Brasil para registrar operações de compra e venda de produtos ou serviços. Esses arquivos XML contêm dados sensíveis como CNPJ, CPF, endereços e nomes de pessoas físicas e jurídicas — que precisam ser anonimizados antes de qualquer uso em pesquisa, análise ou compartilhamento de dados.

### Funcionalidades

- Upload de até **5 arquivos XML** por requisição
- Anonimização em nível de campo para dados sensíveis da NF-e (CNPJ, CPF, endereços, nomes, etc.)
- Anonimização de texto livre no campo `infAdic/infCpl` usando NLP do Presidio (português)
- Visualização **antes / depois** lado a lado na interface web
- Download do XML anonimizado por arquivo

### Arquitetura

```text
UI (porta 3000) -> API Gateway (porta 8000) -> Serviço Presidio (porta 8080)
```

### Pré-requisitos

Antes de começar, você precisa ter instalado na sua máquina:

- [Docker](https://docs.docker.com/get-docker/) (versão 20+)
- [Docker Compose](https://docs.docker.com/compose/install/) (versão 2+)

Para verificar se estão instalados, execute no terminal:

```bash
docker --version
docker compose version
```

### Como executar

#### 1. Clone o repositório

```bash
git clone <url-do-repositorio>
cd api-anon
```

#### 2. (Opcional) Configure variáveis de ambiente

Copie o arquivo de exemplo e ajuste conforme necessário:

```bash
cp env.example .env
```

O arquivo `.env` permite configurar um salt criptográfico personalizado para o hashing dos identificadores. Se não criado, os valores padrão são usados.

#### 3. Suba os containers

```bash
docker compose up --build
```

Na primeira execução, o Docker vai baixar as imagens base e instalar as dependências — isso pode levar alguns minutos. Nas execuções seguintes será muito mais rápido.

Aguarde até ver mensagens como `Application startup complete` nos logs dos três serviços.

#### 4. Acesse a interface

Abra o navegador em:

```
http://localhost:3000
```

#### 5. Verifique se os serviços estão saudáveis

```
http://localhost:8000/health   (API Gateway)
http://localhost:8080/health   (Serviço Presidio)
```

Ambos devem retornar `{"status": "ok"}`.

### Usando a interface web

1. Clique em **"Escolher arquivos"** e selecione entre 1 e 5 arquivos `.xml` de NF-e
2. Clique em **"Process"**
3. Aguarde o processamento (pode levar alguns segundos dependendo do tamanho dos arquivos)
4. Para cada arquivo, a interface exibe:
   - O XML original (à esquerda)
   - O XML anonimizado (à direita)
   - Metadados com os campos modificados
5. Clique em **"Download anonymized XML"** para baixar o arquivo anonimizado

Se não tiver arquivos NF-e disponíveis, a pasta `samples/` contém um exemplo para teste.

### Uso via API

Para integrar a plataforma em outros sistemas, use o endpoint diretamente.

#### `POST /process`

- **URL**: `http://localhost:8000/process`
- **Content-Type**: `multipart/form-data`
- **Campo**: `files` (1 a 5 arquivos `.xml`)

Exemplo com `curl`:

```bash
curl -X POST http://localhost:8000/process \
  -F "files=@caminho/para/nota.xml"
```

Formato da resposta:

```json
{
  "count": 1,
  "results": [
    {
      "filename": "nota.xml",
      "original_xml": "...",
      "anonymized_xml": "...",
      "metadata": {
        "fields_anonymized": ["emit/CNPJ", "dest/CPF"],
        "entities_detected_in_free_text": {"BR_PHONE": 1}
      }
    }
  ]
}
```

### Parando os containers

```bash
docker compose down
```

Para remover também os dados em cache das imagens:

```bash
docker compose down --rmi local
```

### Observações técnicas

- Blocos de assinatura digital XML (`Signature`) são removidos após a anonimização para evitar inconsistências com o conteúdo modificado.
- A implementação padrão usa hashing determinístico com salt para IDs (CNPJ, CPF, chave de acesso) e substituições sintéticas para nomes e endereços.
- Em produção, mantenha o salt em um cofre seguro (ex: HashiCorp Vault, AWS Secrets Manager) e execute a plataforma em infraestrutura privada.

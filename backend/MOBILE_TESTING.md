# Validação móvel isolada

Este fluxo usa exclusivamente `work/mobile-validation.sqlite3`, com um usuário e um imóvel sintéticos. Não copie dados reais para essa base. O script define `DATABASE_URL`, uma chave JWT local e `RADAR_TEST_DISABLE_BACKGROUND_JOBS=1` antes de importar a API; isso evita conectar ao banco configurado em `backend/.env` e desliga scraping, fila de fotos e notificações automáticas.

## Preparar e iniciar a API

No PowerShell, a partir de `C:\Users\gabri_\radar-leilao`:

```powershell
cd backend
.\.venv\Scripts\python.exe .\scripts\prepare_mobile_test.py
$env:DATABASE_URL = 'sqlite:///../work/mobile-validation.sqlite3'
$env:SECRET_KEY = 'local-mobile-validation-only'
$env:RADAR_TEST_DISABLE_BACKGROUND_JOBS = '1'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

O endereço `0.0.0.0` permite conexões da rede virtual do emulador. No Android Emulator, o app já usa `http://10.0.2.2:8000` por padrão. Para uma URL diferente, informe `--dart-define=API_BASE_URL=...`. Confirme a API no navegador do host em `http://127.0.0.1:8000/` antes de abrir o app.

## Testar login e catálogo

Em outro PowerShell, na raiz do repositório, com o emulador inicializado:

```powershell
cd app_flutter
flutter test integration_test/mobile_api_test.dart -d emulator-5554 `
  --dart-define=SMOKE_TEST_EMAIL=mobile.test@example.com `
  --dart-define=SMOKE_TEST_PASSWORD=MobileTest-2026! `
  --dart-define=SMOKE_TEST_PROPERTY_TITLE="Imóvel Sintético Mobile - Teste"
```

Esse teste automatiza somente o login e a presença do imóvel no catálogo. Com o app aberto, confira também manualmente:

1. Buscar `Lisboa` e confirmar que o imóvel sintético permanece; buscar um termo inexistente e confirmar o estado vazio.
2. Em **Mais filtros**, aplicar cidade `Lisboa`, estado `SP`, preço máximo `120000` e desconto mínimo `40`; o imóvel deve permanecer. Limpar os filtros e aplicar.
3. Alternar **Leilões** e **Ordenar** e confirmar que a lista continua carregando. Como a fixture contém um imóvel, ela confirma carregamento, mas não compara a ordem entre resultados.

Para abrir o app manualmente, use `flutter run -d emulator-5554`. A chave e a senha acima são somente para esta base descartável local; não as reutilize.

## Resultado da validação no emulador

O Flutter 3.47.7 e o Dart 3.13.5 estão instalados em `C:\Users\gabri_\AppData\Local\Programs\Flutter\flutter`; o SDK Android e o emulador `emulator-5554` também estão disponíveis. `flutter pub get`, `flutter analyze` e a checagem de formatação concluíram sem problemas. O APK debug foi compilado e instalado no emulador.

O teste de integração `integration_test/mobile_api_test.dart` passou no emulador: login, catálogo, busca com resultado e sem resultado, aplicação/limpeza dos quatro filtros, troca do status do leilão e alteração da ordenação. Todos os pedidos da API usaram somente `work/mobile-validation.sqlite3`, com scraping e tarefas automáticas desativados.

Durante a validação, foi corrigido o overflow do campo de ordenação em telas estreitas, o ciclo de vida dos controladores do painel de filtros e a função SQL `translate` que faltava no SQLite de teste. A expectativa do título do catálogo no teste também foi atualizada para o texto exibido pelo app. `pytest` e `httpx` continuam ausentes no ambiente Python; não foram necessárias mudanças nas dependências do projeto para validar o app Flutter.

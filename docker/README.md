# Environmental Monitoring: servidor

API que lê sensores DHT11/DHT22 ligados ao GPIO de um Raspberry Pi e expõe temperatura e umidade por HTTP, num
container. É consumida pela [integração do Home Assistant](../README.md) e pode ser lida pelo Zabbix.

```text
server/        API (Flask + waitress), Dockerfile e testes
compose.yaml   container no Pi, com acesso ao GPIO
```

Uma única thread no container fala com o GPIO e lê os sensores a cada 30 s, com até 3 tentativas (o DHT11 falha
com frequência). A API devolve a última leitura boa, então as consultas nunca disputam o sensor.

## API

`GET /api/v1/sensors`

```json
{
  "device": {"id": "raspberrypi-envmon", "name": "Raspberry Pi", "version": "2.0.0"},
  "sensors": [
    {
      "id": "sensor_1", "name": "Sensor 1", "model": "DHT11", "pin": "D4",
      "status": "ok", "temperature": 23.9, "humidity": 54.5,
      "last_update": "2026-09-30T16:41:31+00:00", "last_error": null, "consecutive_errors": 0
    }
  ]
}
```

- `status`: `ok`; `stale` quando não há leitura boa há mais de ~3 ciclos (o valor é o último bom); `unavailable`
  quando o sensor nunca respondeu desde que o container subiu.
- `GET /api/v1/sensors/<id>`: um sensor só.
- `GET /health`: `200` enquanto a thread de leitura estiver viva (usado pelo healthcheck do Docker).

Configuração por variáveis de ambiente no `compose.yaml`:

| Variável | Padrão | |
|---|---|---|
| `SENSORS` | `sensor_1:D4:DHT11:Sensor 1,sensor_2:D25:DHT11:Sensor 2` | `id:pino:modelo[:nome]`, modelo `DHT11` ou `DHT22` |
| `READ_INTERVAL` | `30` | segundos entre leituras |
| `DEVICE_ID` | hostname | id estável do Pi no Home Assistant |
| `DEVICE_NAME` | `Environmental Monitoring` | nome do Pi no Home Assistant |
| `SENSOR_BACKEND` | `dht` | `fake` gera valores simulados (desenvolvimento) |
| `BLINKA_FORCEBOARD` / `BLINKA_FORCECHIP` | | força a placa, se a detecção automática falhar |

## Migração no Raspberry Pi

1. Instale o Docker, se ainda não tiver:

   ```bash
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker "$USER"   # saia e entre de novo na sessão
   ```

2. Pare a API antiga, que usa a porta 5000 e o GPIO. Remova do `/etc/crontab` a linha
   `@reboot root cd /home/moinho/temp_hum_tst/ && python3 ./api.py &` e encerre o processo:

   ```bash
   sudo pkill -f 'python3 ./api.py'
   ```

3. Clone o repositório no Pi e suba o container. A primeira build no Pi 3 demora alguns minutos:

   ```bash
   git clone https://github.com/AlexZZeni/ha-envmon.git ~/projects/ha-envmon
   cd ~/projects/ha-envmon/docker
   docker compose up -d --build
   docker compose logs -f
   curl -s localhost:5000/api/v1/sensors
   ```

4. Troque o Zabbix para ler da API (abaixo) antes de desligar o script antigo.

Para atualizar depois: `git pull && docker compose up -d --build` na mesma pasta.

## Zabbix

O script antigo `get_sensor_value.py`, que ainda está no Pi, lê o GPIO direto. Com o container rodando, os dois disputam o mesmo pino e as leituras dos
dois lados falham. Troque os `UserParameter` do agente para consultar a API. As chaves não mudam, então o template
do Zabbix continua igual (`$2` é o número do sensor; `$1` e `$3` passam a ser ignorados):

```bash
sudo apt install -y curl jq
```

```text
UserParameter=externalSensor.humidity[*],curl -fsS --max-time 5 http://127.0.0.1:5000/api/v1/sensors/sensor_$2 | jq -r 'select(.status == "ok") | .humidity'
UserParameter=externalSensor.temperature[*],curl -fsS --max-time 5 http://127.0.0.1:5000/api/v1/sensors/sensor_$2 | jq -r 'select(.status == "ok") | .temperature'
```

Quando a leitura está velha, a saída fica vazia, como acontecia com o script quando o sensor falhava. Depois disso,
os arquivos antigos no Pi (`get_sensor_value.py`, `simple_test.py`, `api.py` e o venv) podem ser apagados.

## Home Assistant

Veja o [`README.md`](../README.md) da raiz. A integração substitui a configuração `rest:` antiga que lia
`/sensors`, que usava o formato anterior da API e para de funcionar com esta versão.

## Problemas comuns

- **`RuntimeError: This module can only be run on a Raspberry Pi!`** ou **`PermissionError` em
  `/proc/device-tree/compatible`**: o container não consegue ler o device tree. Confira se os dois `security_opt` do
  `compose.yaml` (`systempaths=unconfined` e `apparmor=unconfined`) estão lá (precisa de Docker 20.10+). Para testar:
  `docker run --rm --security-opt systempaths=unconfined --security-opt apparmor=unconfined environmental-monitoring
  cat /proc/device-tree/model` deve mostrar o modelo do Pi.
- **`consecutive_errors` sobe sempre e `last_error` fala de permissão ou GPIO**: troque `devices` e `security_opt`
  do `compose.yaml` por `privileged: true`. Se funcionar, o problema é acesso a dispositivo e não o sensor.
- **`Checksum did not validate` ou `A full buffer was not returned` de vez em quando**: é normal no DHT11. As
  tentativas cobrem isso; só é problema se o `status` ficar `stale`.

## Desenvolvimento

```bash
cd server
python -m venv venv && ./venv/bin/pip install -r requirements.txt pytest
./venv/bin/pytest
SENSOR_BACKEND=fake ./venv/bin/python app.py
```

## Referências

- <https://github.com/adafruit/Adafruit_CircuitPython_DHT>
- <https://www.raspberrypi.com/documentation/computers/raspberry-pi.html>

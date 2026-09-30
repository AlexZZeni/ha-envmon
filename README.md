# Environmental Monitoring para Home Assistant

Temperatura e umidade de sensores DHT11/DHT22 ligados a um Raspberry Pi, no Home Assistant.

O repositório tem as duas pontas:

- **[`docker/`](docker/README.md)**: API que roda num container no Raspberry Pi, lê os sensores pelo GPIO e expõe
  as leituras por HTTP. Suba ela primeiro.
- **`custom_components/envmon/`**: integração do Home Assistant que consome essa API. É a única parte que o HACS
  instala.

A integração cria:

- um dispositivo para o Pi (**Raspberry Pi**);
- um dispositivo por sensor DHT, ligado ao Pi, com **Temperatura** e **Umidade**.

Se o sensor para de responder por vários ciclos (`status` diferente de `ok` na API), as entidades ficam
**indisponíveis** em vez de mostrar o último valor como se fosse atual. Novos sensores no `SENSORS` do container
aparecem depois de recarregar a integração.

## Instalação

1. Suba o container no Raspberry Pi seguindo o [`docker/README.md`](docker/README.md).
2. No HACS: ⋮ → **Repositórios personalizados** → `https://github.com/AlexZZeni/ha-envmon`, categoria
   **Integração**. Procure **Environmental Monitoring**, instale e reinicie o Home Assistant.

   Sem HACS: copie `custom_components/envmon/` para `config/custom_components/envmon/` e reinicie.
3. **Configurações → Dispositivos e serviços → Adicionar integração → Environmental Monitoring**, informando o IP do
   Pi e a porta (`5000`).

Se usava uma configuração `rest:`/`template:` antiga lendo `/sensors` (`pi_dht_raw`, `pi_sensor_*`), remova-a do
`configuration.yaml`: o formato da API mudou e ela não funciona mais.

## Desenvolvimento

```sh
python -m venv venv && ./venv/bin/pip install pytest-homeassistant-custom-component
./venv/bin/pytest
```

Os testes do servidor ficam em `docker/server/` (ver [`docker/README.md`](docker/README.md#desenvolvimento)).

# Futura ERP — Tabela de Versões por BUILD_BD

> Consulte a versão do sistema a partir do campo `BUILD_BD` da tabela `PARAMETROS`.
> Pegue os **2 ou 3 primeiros dígitos** do `BUILD_BD` para identificar o prefixo e encontrar a versão.

## Como usar

```sql
SELECT BUILD_BD FROM PARAMETROS;
```

Exemplo: `BUILD_BD = 114035` → prefixo **114** → versão **2026.02.09**

## Legenda

| Status | Descrição |
|--------|-----------|
| ✅ Real | Dado histórico confirmado pelo fornecedor |
| 🔵 Confirmado | Verificado em banco de dados real |
| ⚪ Estimado | Calculado com base no intervalo médio de ~42 dias/release |

---

## 2015

| BUILD_BD (prefixo) | Versão | Status |
|--------------------|--------|--------|
| 57xxx | 2015.12.02 | ✅ Real |

## 2016

| BUILD_BD (prefixo) | Versão | Status |
|--------------------|--------|--------|
| 58xxx | 2016.02.15 | ✅ Real |
| 60xxx | 2016.03.14 | ✅ Real |
| 72xxx | 2016.04.11 | ✅ Real |
| 80xxx | 2016.05.09 | ✅ Real |
| 91xxx | 2016.06.06 | ✅ Real |
| 91xxx | 2016.07.04 | ✅ Real |
| 100xxx | 2016.08.01 | ✅ Real |
| 110xxx | 2016.08.29 | ✅ Real |
| 122xxx | 2016.09.26 | ✅ Real |
| 130xxx | 2016.10.24 | ✅ Real |
| 140xxx | 2016.11.21 | ✅ Real |

## 2017

| BUILD_BD (prefixo) | Versão | Status |
|--------------------|--------|--------|
| 150xxx | 2017.01.16 | ✅ Real |
| 160xxx | 2017.02.13 | ✅ Real |
| 170xxx | 2017.03.13 | ✅ Real |
| 180xxx | 2017.04.10 | ✅ Real |
| 190xxx | 2017.05.08 | ✅ Real |
| 203xxx | 2017.06.05 | ✅ Real |
| 210xxx | 2017.07.03 | ✅ Real |
| 220xxx | 2017.07.31 | ✅ Real |
| 230xxx | 2017.08.28 | ✅ Real |
| 250xxx | 2017.09.25 | ✅ Real |
| 260xxx | 2017.10.23 | ✅ Real |
| 271xxx | 2017.11.20 | ✅ Real |

## 2018

| BUILD_BD (prefixo) | Versão | Status |
|--------------------|--------|--------|
| 281xxx | 2018.01.29 | ✅ Real |
| 291xxx | 2018.02.26 | ✅ Real |
| 316xxx | 2018.03.26 | ✅ Real |
| 320xxx | 2018.04.23 | ✅ Real |
| 331xxx | 2018.05.21 | ✅ Real |
| 340xxx | 2018.06.18 | ✅ Real |
| 350xxx | 2018.07.16 | ✅ Real |
| 360xxx | 2018.08.13 | ✅ Real |
| 370xxx | 2018.09.10 | ✅ Real |
| 380xxx | 2018.10.08 | ✅ Real |
| 390xxx | 2018.11.05 | ✅ Real |
| 400xxx | 2018.12.03 | ✅ Real |

## 2019

| BUILD_BD (prefixo) | Versão | Status |
|--------------------|--------|--------|
| 410xxx | 2019.01.28 | ✅ Real |
| 421xxx | 2019.02.25 | ✅ Real |
| 430xxx | 2019.03.25 | ✅ Real |
| 440xxx | 2019.04.22 | ✅ Real |
| 450xxx | 2019.05.20 | ✅ Real |
| 460xxx | 2019.06.17 | ✅ Real |
| 470xxx | 2019.07.15 | ✅ Real |
| 480xxx | 2019.08.12 | ✅ Real |
| 491xxx | 2019.09.09 | ✅ Real |
| 500xxx | 2019.10.07 | ✅ Real |
| 510xxx | 2019.11.04 | ✅ Real |
| 520xxx | 2019.12.02 | ✅ Real |

## 2020

| BUILD_BD (prefixo) | Versão | Status |
|--------------------|--------|--------|
| 530xxx | 2020.01.27 | ✅ Real |
| 590xxx | 2020.02.24 | ✅ Real |
| 610xxx | 2020.04.20 | ✅ Real |
| 620xxx | 2020.05.18 | ✅ Real |
| 630xxx | 2020.06.15 | ✅ Real |
| 640xxx | 2020.07.13 | ✅ Real |
| 650xxx | 2020.08.01 | ✅ Real |
| 660xxx | 2020.09.01 | ✅ Real |
| 670xxx | 2020.10.01 | ✅ Real |
| 680xxx | 2020.11.02 | ✅ Real |
| 690xxx | 2020.11.30 | ✅ Real |

## 2021

| BUILD_BD (prefixo) | Versão | Status |
|--------------------|--------|--------|
| 700xxx | 2021.02.01 | ✅ Real |
| 710xxx | 2021.03.01 | ✅ Real |
| 720xxx | 2021.03.29 | ✅ Real |
| 730xxx | 2021.04.26 | ✅ Real |
| 740xxx | 2021.06.07 | ⚪ Estimado |
| 750xxx | 2021.07.20 | ⚪ Estimado |
| 760xxx | 2021.09.01 | ⚪ Estimado |
| 770xxx | 2021.10.13 | ⚪ Estimado |
| 780xxx | 2021.11.25 | ⚪ Estimado |

## 2022

| BUILD_BD (prefixo) | Versão | Status |
|--------------------|--------|--------|
| 790xxx | 2022.01.07 | ⚪ Estimado |
| 800xxx | 2022.02.18 | ⚪ Estimado |
| 810xxx | 2022.04.02 | ⚪ Estimado |
| 820xxx | 2022.05.15 | ⚪ Estimado |
| 830xxx | 2022.06.26 | ⚪ Estimado |
| 840xxx | 2022.08.08 | ⚪ Estimado |
| 850xxx | 2022.09.20 | ⚪ Estimado |
| 860xxx | 2022.11.01 | ⚪ Estimado |
| 870xxx | 2022.12.14 | ⚪ Estimado |

## 2023

| BUILD_BD (prefixo) | Versão | Status |
|--------------------|--------|--------|
| 880xxx | 2023.01.26 | ⚪ Estimado |
| 890xxx | 2023.03.09 | ⚪ Estimado |
| 900xxx | 2023.04.21 | ⚪ Estimado |
| 910xxx | 2023.06.03 | ⚪ Estimado |
| 920xxx | 2023.07.15 | ⚪ Estimado |
| 930xxx | 2023.08.27 | ⚪ Estimado |
| 940xxx | 2023.10.09 | ⚪ Estimado |
| 950xxx | 2023.11.21 | ⚪ Estimado |

## 2024

| BUILD_BD (prefixo) | Versão | Status |
|--------------------|--------|--------|
| 960xxx | 2024.01.02 | ⚪ Estimado |
| 970xxx | 2024.02.14 | ⚪ Estimado |
| 980xxx | 2024.03.28 | ⚪ Estimado |
| 990xxx | 2024.05.09 | ⚪ Estimado |
| 100xxx | 2024.06.21 | ⚪ Estimado |
| 101xxx | 2024.08.03 | ⚪ Estimado |
| 102xxx | 2024.09.14 | ⚪ Estimado |
| 103xxx | 2024.10.27 | ⚪ Estimado |
| 104xxx | 2024.12.09 | ⚪ Estimado |

## 2025

| BUILD_BD (prefixo) | Versão | Status |
|--------------------|--------|--------|
| 105xxx | 2025.01.20 | ⚪ Estimado |
| 106xxx | 2025.03.04 | ⚪ Estimado |
| 107xxx | 2025.04.16 | ⚪ Estimado |
| 108xxx | 2025.05.28 | ⚪ Estimado |
| 109xxx | 2025.07.10 | ⚪ Estimado |
| 110xxx | 2025.08.22 | ⚪ Estimado |
| 111xxx | 2025.10.03 | ⚪ Estimado |
| 112xxx | 2025.11.15 | ⚪ Estimado |
| 113xxx | 2025.12.28 | ⚪ Estimado |

## 2026

| BUILD_BD (prefixo) | Versão | Status |
|--------------------|--------|--------|
| 114xxx | 2026.02.09 | 🔵 Confirmado |
| 115xxx | 2026.03.23 | ⚪ Estimado |
| 116xxx | 2026.05.05 | ⚪ Estimado |
| 117xxx | 2026.06.17 | ⚪ Estimado |
| 118xxx | 2026.07.29 | ⚪ Estimado |
| 119xxx | 2026.09.10 | ⚪ Estimado |
| 120xxx | 2026.10.23 | ⚪ Estimado |
| 121xxx | 2026.12.04 | ⚪ Estimado |

## 2027

| BUILD_BD (prefixo) | Versão | Status |
|--------------------|--------|--------|
| 122xxx | 2027.01.16 | ⚪ Estimado |
| 123xxx | 2027.02.28 | ⚪ Estimado |
| 124xxx | 2027.04.11 | ⚪ Estimado |
| 125xxx | 2027.05.24 | ⚪ Estimado |
| 126xxx | 2027.07.06 | ⚪ Estimado |
| 127xxx | 2027.08.17 | ⚪ Estimado |
| 128xxx | 2027.09.29 | ⚪ Estimado |
| 129xxx | 2027.11.11 | ⚪ Estimado |
| 130xxx | 2027.12.23 | ⚪ Estimado |

## 2028

| BUILD_BD (prefixo) | Versão | Status |
|--------------------|--------|--------|
| 131xxx | 2028.02.04 | ⚪ Estimado |
| 132xxx | 2028.03.18 | ⚪ Estimado |
| 133xxx | 2028.04.29 | ⚪ Estimado |
| 134xxx | 2028.06.11 | ⚪ Estimado |
| 135xxx | 2028.07.24 | ⚪ Estimado |
| 136xxx | 2028.09.05 | ⚪ Estimado |
| 137xxx | 2028.10.17 | ⚪ Estimado |
| 138xxx | 2028.11.29 | ⚪ Estimado |

## 2029

| BUILD_BD (prefixo) | Versão | Status |
|--------------------|--------|--------|
| 139xxx | 2029.01.11 | ⚪ Estimado |
| 140xxx | 2029.02.22 | ⚪ Estimado |
| 141xxx | 2029.04.06 | ⚪ Estimado |
| 142xxx | 2029.05.19 | ⚪ Estimado |
| 143xxx | 2029.06.30 | ⚪ Estimado |
| 144xxx | 2029.08.12 | ⚪ Estimado |
| 145xxx | 2029.09.24 | ⚪ Estimado |
| 146xxx | 2029.11.05 | ⚪ Estimado |
| 147xxx | 2029.12.18 | ⚪ Estimado |

## 2030

| BUILD_BD (prefixo) | Versão | Status |
|--------------------|--------|--------|
| 148xxx | 2030.01.30 | ⚪ Estimado |
| 149xxx | 2030.03.13 | ⚪ Estimado |
| 150xxx | 2030.04.25 | ⚪ Estimado |
| 151xxx | 2030.06.07 | ⚪ Estimado |
| 152xxx | 2030.07.19 | ⚪ Estimado |
| 153xxx | 2030.08.31 | ⚪ Estimado |
| 154xxx | 2030.10.13 | ⚪ Estimado |
| 155xxx | 2030.11.25 | ⚪ Estimado |

## 2031

| BUILD_BD (prefixo) | Versão | Status |
|--------------------|--------|--------|
| 156xxx | 2031.01.06 | ⚪ Estimado |
| 157xxx | 2031.02.18 | ⚪ Estimado |
| 158xxx | 2031.04.02 | ⚪ Estimado |
| 159xxx | 2031.05.14 | ⚪ Estimado |
| 160xxx | 2031.06.26 | ⚪ Estimado |
| 161xxx | 2031.08.08 | ⚪ Estimado |
| 162xxx | 2031.09.19 | ⚪ Estimado |
| 163xxx | 2031.11.01 | ⚪ Estimado |
| 164xxx | 2031.12.14 | ⚪ Estimado |

## 2032

| BUILD_BD (prefixo) | Versão | Status |
|--------------------|--------|--------|
| 165xxx | 2032.01.25 | ⚪ Estimado |
| 166xxx | 2032.03.08 | ⚪ Estimado |
| 167xxx | 2032.04.20 | ⚪ Estimado |
| 168xxx | 2032.06.01 | ⚪ Estimado |
| 169xxx | 2032.07.14 | ⚪ Estimado |
| 170xxx | 2032.08.26 | ⚪ Estimado |
| 171xxx | 2032.10.07 | ⚪ Estimado |
| 172xxx | 2032.11.19 | ⚪ Estimado |

## 2033

| BUILD_BD (prefixo) | Versão | Status |
|--------------------|--------|--------|
| 173xxx | 2033.01.01 | ⚪ Estimado |
| 174xxx | 2033.02.12 | ⚪ Estimado |
| 175xxx | 2033.03.27 | ⚪ Estimado |
| 176xxx | 2033.05.09 | ⚪ Estimado |
| 177xxx | 2033.06.21 | ⚪ Estimado |
| 178xxx | 2033.08.02 | ⚪ Estimado |
| 179xxx | 2033.09.14 | ⚪ Estimado |
| 180xxx | 2033.10.27 | ⚪ Estimado |
| 181xxx | 2033.12.08 | ⚪ Estimado |

## 2034

| BUILD_BD (prefixo) | Versão | Status |
|--------------------|--------|--------|
| 182xxx | 2034.01.20 | ⚪ Estimado |
| 183xxx | 2034.03.04 | ⚪ Estimado |
| 184xxx | 2034.04.15 | ⚪ Estimado |
| 185xxx | 2034.05.28 | ⚪ Estimado |
| 186xxx | 2034.07.10 | ⚪ Estimado |
| 187xxx | 2034.08.21 | ⚪ Estimado |
| 188xxx | 2034.10.03 | ⚪ Estimado |
| 189xxx | 2034.11.15 | ⚪ Estimado |
| 190xxx | 2034.12.27 | ⚪ Estimado |

## 2035

| BUILD_BD (prefixo) | Versão | Status |
|--------------------|--------|--------|
| 191xxx | 2035.02.08 | ⚪ Estimado |
| 192xxx | 2035.03.23 | ⚪ Estimado |
| 193xxx | 2035.05.04 | ⚪ Estimado |
| 194xxx | 2035.06.16 | ⚪ Estimado |
| 195xxx | 2035.07.29 | ⚪ Estimado |
| 196xxx | 2035.09.10 | ⚪ Estimado |
| 197xxx | 2035.10.22 | ⚪ Estimado |
| 198xxx | 2035.12.04 | ⚪ Estimado |

## 2036

| BUILD_BD (prefixo) | Versão | Status |
|--------------------|--------|--------|
| 199xxx | 2036.01.16 | ⚪ Estimado |
| 200xxx | 2036.02.27 | ⚪ Estimado |
| 201xxx | 2036.04.10 | ⚪ Estimado |
| 202xxx | 2036.05.23 | ⚪ Estimado |
| 203xxx | 2036.07.04 | ⚪ Estimado |
| 204xxx | 2036.08.16 | ⚪ Estimado |
| 205xxx | 2036.09.28 | ⚪ Estimado |
| 206xxx | 2036.11.09 | ⚪ Estimado |
| 207xxx | 2036.12.22 | ⚪ Estimado |

---

*Gerado automaticamente. Intervalo médio entre releases: ~42 dias.*
*Âncoras confirmadas: `73xxx` = 2021.04.26 | `114xxx` = 2026.02.09*
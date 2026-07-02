# Lánareiknir — verðtryggt eða óverðtryggt?

Reiknivél og greiningartól sem ber saman verðtryggð og óverðtryggð húsnæðislán
— og svarar spurningunni:

**Hvað gerist ef þú tekur verðtryggt lán en greiðir samt jafn háa mánaðargreiðslu
og óverðtryggða lánið hefði krafist?** Mismunurinn fer þá sem aukaafborgun inn á
höfuðstólinn í hverjum mánuði.

## Prófaðu reiknivélina

Opnaðu https://github.com/arnarjokull00-ui/lanareiknir í vafra — engin uppsetning.
Þú stillir höfuðstól, vexti, verðbólgu og mánaðargreiðslu og sérð strax hvor
leiðin vinnur, hvenær lánið greiðist upp og hvað jöfn eignamyndun kostar miðað við verðbólgu.

## Helstu niðurstöður

**Allt veltur á verðbólgunni.** Miðað við 4% raunvexti og 9% nafnvexti liggur
jafnvægið við um það bil 5,5% meðalverðbólgu yfir lánstímann. Undir því vinnur
verðtryggða leiðin með aukagreiðslum — yfir því vinnur óverðtryggða lánið.
Verðbólgumarkmið Seðlabankans er 2,5%.

**Sagan 2015–2025:** keyrt á raunverulegri verðbólgu (Hagstofan) og
stýrivaxtaferli tímabilsins — þar með talið verðbólgutímabilið 2022–2023 — er
niðurstaðan háð vaxtaálagi óverðtryggða lánsins, sem ræðst af veðhlutfalli:

| Vaxtaálag (veðhlutfall) | Hvor vann? | Munur |
|---|---|---|
| 2,25% (lágt veðhlutfall) | Óverðtryggt | 0,4 m.kr. |
| 3,00% (miðlungs) | Verðtryggt + aukagreiðslur | 3,2 m.kr. |
| 3,35% (hátt veðhlutfall) | Verðtryggt + aukagreiðslur | 4,9 m.kr. |


**Að greiða bara lágmarkið af verðtryggðu láni** reyndist dýrasta leiðin í
öllum sviðsmyndum.

## Fyrir bakprófun

```bash
pip install numpy pandas pytest requests
python -m pytest tests/              # 8 próf
python -m lanareiknir.backtest       # söguleg keyrsla + næmnigreining
```

Python-vélin (`lanareiknir/`) styður bæði jafnar greiðslur og jafnar
afborganir, sögulegar verðbólgu- og vaxtaslóðir, og sækir vísitölu neysluverðs
beint frá Hagstofunni. 

## Fyrirvari

Þetta er reiknilíkan, ekki fjármálaráðgjöf. Berðu allar niðurstöður saman við
raunveruleg vaxtakjör og skilmála frá þínum banka.

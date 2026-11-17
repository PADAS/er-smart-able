# Hali

Programu inaonyesha hali kwa Kiingereza; hapa zinatolewa jinsi zinavyoonekana.

## Uingizaji

| Hali | Maana |
|---|---|
| <code>planning</code> | Mpango unatengenezwa. Hauandiki chochote. |
| <code>planned</code> | Mpango uko tayari kusomwa na kuthibitishwa. |
| <code>queued</code> | Umethibitishwa; utekelezaji umeombwa na unakaribia kuanza. |
| <code>running</code> | Utekelezaji unapitia hatua zake. Ukurasa unajisasisha wenyewe kila baada ya sekunde chache. |
| <code>continuing</code> | Utekelezaji ulifikia kikomo cha saa 22 na ukakabidhi kazi kwa utekelezaji mpya unaoendelea pale ulipoishia. Angalia *Utekelezaji mrefu na mwendelezo*. |
| <code>needs_attention</code> | Utekelezaji ulisimama kwenye tokeo linalozuia, au ulimalizika ukiwa na doria zilizoshindwa. Soma matokeo, rekebisha tovuti, kisha bonyeza **Continue** (endelea). |
| <code>done</code> | Kila doria iko kwenye tovuti. |
| <code>failed</code> | Kazi ilikumbana na hitilafu ambayo haikuweza kuitatua. Hitilafu na kumbukumbu viko kwenye ukurasa. Baada ya kurekebisha chanzo, bonyeza **Plan again** (panga tena); mpango mpya unaonyesha kilichobaki na unatoa Confirm. (Continue ni kwa ajili tu ya uingizaji uliosimama kwa sababu ya matokeo, au ambao kazi yake ilikatizwa.) |

## Hatua

| Hali | Maana |
|---|---|
| pending (inasubiri) | Bado haijafikiwa katika utekelezaji huu. |
| running (inaendelea) | Inaendelea, pamoja na muda uliotumika hadi sasa. |
| done (imekamilika) | Imekamilika, pamoja na muda iliochukua na ilichofanya. |
| stopped (imesimama) | Kanuni ya kusimama ilimaliza utekelezaji hapa: tokeo linalozuia baada ya hatua hii. |
| failed (imeshindwa) | Hitilafu katika hatua hii ilimaliza utekelezaji. |
| interrupted (imekatizwa) | Kazi ilikatizwa kabla ya kuweza kutoa taarifa; muda wa kufuli yake (hold) umeisha na **Continue** inapatikana. |
| not reached (haijafikiwa) | Hatua ya baadaye ya utekelezaji uliosimama au kushindwa mapema. |

## Ishara ya uhai

Chini ya jedwali la hatua, wakati uingizaji unaendelea, mstari mmoja unaeleza utekelezaji huu umeendelea kwa muda gani na ni muda gani umepita tangu kazi ilipotoa taarifa mara ya mwisho. Kazi inatoa taarifa kila hatua inapobadilika na angalau kila sekunde thelathini wakati wa uingizaji, kwa hiyo muda wa "last reported" unaoendelea kuongezeka kupita dakika chache unamaanisha kazi imekwama au imetoweka.

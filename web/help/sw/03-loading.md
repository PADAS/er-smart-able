# Kuingiza seti ya data

Uingizaji unaweka eneo moja la hifadhi kutoka seti moja ya data kwenye tovuti moja. Uanzishe kutoka kwenye ukurasa wa seti ya data kwa **Load into EarthRanger** (ingiza kwenye EarthRanger), kwenye kichupo cha Overview au Loads, ukichagua eneo la hifadhi, tovuti, lugha ya lebo, modeli inayoweza kusanidiwa (si lazima), kundi (orodha ya askari) ambamo askari wanachaguliwa, na kundi la matukio.

## Mpango kwanza, kisha thibitisha

Kila uingizaji unaanza kama **mpango**: jaribio linalowasiliana na tovuti lakini haliandiki chochote. Unaonyesha kile ambacho utekelezaji halisi ungeunda, kusasisha au kuzima, matokeo ambayo ungesimama kwayo, na doria ambazo ungeziingiza. Usome, kisha bonyeza **Confirm and load** (thibitisha na uingize). Kama mpango tayari unaonyesha matokeo yanayozuia, kitufe kinaeleza mahali utekelezaji utakaposimama; hata hivyo utekelezaji unaandika kila kitu kilicho kabla ya hapo, kwa hiyo kuthibitisha ndiyo njia ya kawaida ya kusonga mbele.

## Hatua nne

Utekelezaji unapitia hatua kwa mpangilio. Kila hatua inaweza kurudiwa bila madhara: utekelezaji wa pili unaifanya tena na kufikia kilichobaki.

| Hatua | Inachoandika kwenye EarthRanger |
|---|---|
| **Event types** (aina za matukio) | Kundi la matukio na aina moja ya tukio kwa kila kategoria ya SMART, pamoja na sehemu zake na orodha zake za machaguo, kutoka kwenye moduli data (na modeli inayoweza kusanidiwa, kama ilichaguliwa). Aina zilizopo zinasasishwa, hazirudufishwi. |
| **Patrol setup** (mpangilio wa doria) | Aina za doria, sehemu za jumla za doria, wahusika askari (mmoja kwa kila mfanyakazi wa SMART aliyefanya doria), uanachama wao katika kundi la orodha ya askari, na machaguo ya vituo (stations). Chochote ambacho API haiwezi kufanya kinakuwa tokeo: timu, aikoni, ruhusa. |
| **Preflight** (ukaguzi wa awali) | Hauandiki chochote. Unakagua kwamba tovuti ina kila kitu ambacho doria zinahitaji: aina za doria, timu, wahusika, aina za matukio, sehemu. |
| **Patrols** (doria) | Doria zenyewe, kila moja ikiwa na vituo vyake vya doria (legs), wanachama wake, alama yake na matukio kutoka kwenye vielekezi (waypoints) vyake. Daftari la kumbukumbu linaandika kila doria inapofika, kwa hiyo utekelezaji unaweza kuendelezwa bila kurudufisha chochote. |

## Kanuni ya kusimama

Baada ya mpangilio wa doria na baada ya ukaguzi wa awali, utekelezaji unasimama kama tokeo lolote **linazuia**. Hali ya uingizaji inakuwa `needs_attention` na matokeo yanaeleza la kufanya. Hakuna kilichokwisha kuandikwa kinachotenduliwa. Rekebisha tovuti, kisha bonyeza **Continue** (endelea): utekelezaji unaanza tena kutoka hatua ya kwanza, jambo ambalo ni la haraka kwa sababu kila kitu kipo tayari, na unafikia doria.

**Maonyo** hayasimamishi utekelezaji kamwe. Yanaweka kumbukumbu ya jambo linalofaa kujulikana, kama vile kategoria iliyostaafishwa au kielekezi (waypoint) ambacho matukio yake hayawezi kuwekwa pamoja.

Doria zinazoshindwa wakati wa uingizaji hazisimamishi nyingine. Mwishoni zinakuwa tokeo moja linalozuia linaloorodhesha kila hitilafu; **Continue** inajaribu tena doria hizo tu.

## Kundi la matukio

Kundi la matukio ni kitambulisho cha EarthRanger ambacho moduli data inatumwa chini yake. Chaguo-msingi ni `smart-<conservation area id>`. Kama moduli data ya eneo hili la hifadhi ilishatumwa kwenye tovuti, kwa mfano kwa zana ya mstari wa amri, tumia kitambulisho kilichotumiwa wakati huo, ili aina za matukio zisasishwe badala ya kuundwa mara ya pili chini ya kundi jipya.

## Kuingiza sehemu ya seti ya data

**What to load** (cha kuingiza), kwenye kisanduku cha mazungumzo cha uingizaji, ina machaguo mawili.

- **The data model and patrols** (moduli data na doria), ambalo ndilo chaguo-msingi. Acha **Patrols from** na **to** (doria kuanzia… hadi…) wazi ili kuingiza kila doria, au jaza moja au zote mbili ili kuingiza tu doria zinazoanza siku hizo au kati yake. Vielelezo, picha na alama ya doria vinakuja pamoja nayo. Tarehe ni za eneo la hifadhi lenyewe, jinsi SMART ilivyozirekodi. Doria ambayo SMART iliihifadhi bila tarehe ya kuanza inaachwa nje ya kipindi chochote. Kipindi kinapunguza doria tu: uingizaji bado unaweka moduli data nzima, kwa hiyo hatua unazomwomba msimamizi azifanye, kama kuunda timu, zinahusu kila timu ya eneo la hifadhi, zikiwemo timu zilizotumiwa na doria za zamani tu.
- **The data model only** (moduli data pekee): aina za matukio, aina za doria na sehemu zake, askari wakiwa wahusika, na orodha ya askari. Hicho ndicho timu inachohitaji ili kuanza kufanya doria na kurekodi kwenye EarthRanger bila kuleta historia yake. Bado unasimama kwenye jambo lolote ambalo msimamizi lazima alifanye kwanza kwenye tovuti, kama kuunda timu.

Uingizaji wa baadaye kwenye tovuti ileile unaweza kupanua kipindi au kuongeza doria. Chochote kilichokwisha kuingizwa kinarukwa. Ukurasa wa uingizaji na kichupo cha Loads cha seti ya data vinataja kile ambacho kila uingizaji uliandika, kwa mfano "Data model only" au "Patrols from 2023-01-01 to 2024-12-31".

## Utekelezaji mrefu na mwendelezo

Utekelezaji unaingiza kwanza kila doria pamoja na vielelezo vyake na picha zake, kisha alama za kila doria. Upau wa maendeleo unaonyesha awamu uliyomo, kasi yake, na muda uliobaki katika awamu hiyo.

Muda ambao utekelezaji unachukua unategemea kasi ya tovuti ya EarthRanger kuandika, si smart-able. Kila kielelezo kinachukua takriban sekunde 0.8, na nukta za alama zinaongeza kidogo, kwa hiyo eneo la hifadhi lenye vielelezo 70,000 linachukua takriban siku moja. Uingizaji miwili kwenye tovuti mbili tofauti unaendelea sambamba kwa kasi kamili; miwili kwenye tovuti moja ungepunguziana kasi tu.

Kazi ya Cloud Run inaweza kuendelea kwa saa 24 tu, kwa hiyo ifikapo saa 22 kazi inaacha kuchukua doria mpya, inamaliza iliyo njiani, inahifadhi daftari lake la kumbukumbu, na inaanzisha utekelezaji mpya wa yenyewe. Hali ya uingizaji ni `continuing` wakati hilo linatokea, na ukurasa unataja mwendelezo unaoupimia muda. Hakuna kinachopotea na hakuna kinachoingizwa mara mbili. Uingizaji unaweza kuendelea hadi mara kumi kabla ya kuwekwa alama ya kushindwa; hiyo ni zaidi sana ya kile ambacho seti yoyote ya data inahitaji.

Kazi ikikatizwa ghafla, kwa mfano kwa hitilafu ya huduma, haiwezi kutoa taarifa. Uingizaji unabaki na hali yake ya mwisho hadi muda wa kushikiliwa kwake uishe, takriban saa 25 baada ya kazi kuanza, kisha ukurasa unatoa **Continue**, inayoendeleza kutoka kwenye daftari la kumbukumbu.

## Kuwapa askari akaunti {#rangers-accounts}

Mpangilio wa doria unaunda mhusika mmoja kwa kila mfanyakazi wa SMART anayeonekana kwenye doria au ambaye bado ameajiriwa, na uingizaji unaweka doria zake, alama zake na ripoti zake kwa mhusika huyo. Askari atakayetumia EarthRanger Mobile baadaye anahitaji akaunti ya mtumiaji **iliyounganishwa na mhusika huyo**: alama za mtumiaji zinakwenda kwa mhusika aliyeunganishwa naye, na matukio anayoripoti yanamtaja kama *reported by* (ameripoti). Bila muunganisho huo, kuingia kwake mara ya kwanza kunaunda mhusika wa pili na historia inagawanyika.

Sehemu ya **Rangers** (askari) ya ukurasa wa uingizaji, na kichupo cha **Rangers** cha seti ya data (kinachoonyesha uingizaji wa karibuni zaidi uliofikia mpangilio wa doria), vinaorodhesha kila mmoja wa watu hao, pamoja na jina jinsi lilivyo hasa kwenye tovuti, kama mtu huyo bado yuko hai kazini kwenye SMART, na idadi mbili za doria: katika doria ambazo uingizaji huu unaziingiza (kipindi chake cha tarehe, kama kiliwekwa) na katika seti nzima ya data. Askari ambaye bado ameajiriwa na hana doria anaonyesha 0, na uingizaji wa moduli data pekee, ambao hauingizi doria, unaonyesha tu idadi ya seti nzima ya data. Faili ya CSV ya kupakua ina mistari ileile pamoja na safu tupu ya barua pepe.

Mstari wenye alama *employee record deleted in SMART* (rekodi ya mfanyakazi imefutwa kwenye SMART) ni mwanachama wa doria ambaye rekodi yake ya mfanyakazi haipo tena; mhusika wake amepewa jina la kitambulisho. Hakuna anayeweza kuingia kwa jina lake, kwa hiyo hahitaji akaunti.

Ili kumpa askari akaunti, kwenye usimamizi wa Django fungua **Users › add**, andika jina jinsi lilivyoorodheshwa, na kwenye sehemu ya **linked subject** chagua mhusika wake kwa jina hilo. Fanya hivi kabla hajaingia. Kwa sasa muunganisho unaweza kufanywa kutoka upande wa mtumiaji tu, na msimamizi pekee.

Kama akaunti zinaundwa kwa njia nyingine, hakikisha jina la kwanza na la mwisho la mtumiaji yanalingana kabisa na jina la mhusika na kwamba mpangilio wa mhusika wa mtoa chanzo wa ER Track ni "use existing": EarthRanger kisha inamuunganisha mhusika askari anapoingia mara ya kwanza kwa kulinganisha jina. Jina linalotofautiana kwa herufi moja linapata mhusika mpya, mtupu, badala yake.

## Panga tena na futa

**Plan again** (panga tena) inaendesha mpango mpya kwa uingizaji uliopangwa, uliosimama, ulioshindwa au uliokamilika, kwa mfano baada ya kurekebisha tovuti, ili kuona kilichobaki. **Delete this load** (futa uingizaji huu) inaondoa rekodi ya smart-able ya uingizaji huo, daftari lake la kumbukumbu, mpango wake na kumbukumbu zake. Haiondoi chochote kwenye EarthRanger.

Ni uingizaji mmoja tu wa eneo fulani la hifadhi kwenye tovuti fulani unaoweza kuwa hai kwa wakati mmoja. Kuanzisha mwingine kunakataliwa hadi wa kwanza umalizike au usimame.

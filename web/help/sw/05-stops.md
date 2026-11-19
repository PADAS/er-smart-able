# Uingizaji unaposimama

Utekelezaji unasimama pale ambapo tovuti inahitaji jambo ambalo API haiwezi kulifanya, au pale ambapo tovuti haiko tayari kwa doria. Kila tokeo la ukaguzi (finding) kwenye ukurasa wa uingizaji linataja la kufanya; maelezo yaliyo hapa yanatoa agizo lilelile kwa maelezo marefu zaidi. Thamani ambazo tokeo linazionyesha pamoja na kitufe cha kunakili lazima zitumike jinsi zilivyo hasa, herufi kwa herufi: EarthRanger inazilinganisha kwa jina.

Majina ya menyu za usimamizi wa EarthRanger yanatolewa kwa Kiingereza, jinsi yanavyoonekana humo.

Baada ya kurekebisha tovuti, bonyeza **Endelea**. Utekelezaji unarudia hatua za mwanzo, jambo ambalo ni la haraka, kisha unaendelea.

## Maandalizi ya doria

### Unda timu ya doria {#finding-team}

Doria za SMART zinataja timu; API ya EarthRanger haiwezi kuunda timu. Kwenye usimamizi wa Django, fungua **Patrol configuration › Teams** na uongeze timu ambayo sehemu yake ya *display* ni jina la timu lililoonyeshwa, kama lilivyo hasa. Tokeo linaorodhesha wanachama wa timu kwenye SMART, kwa taarifa yako; uingizaji unaitambua timu kwa jina lake tu. Kuna ingizo moja kwa kila timu inayokosekana; ziunde zote, kisha bonyeza **Endelea**.

### Waweke askari kwenye kundi la wahusika la orodha ya askari {#finding-roster_group}

Hakuna kundi la orodha ya askari lililotajwa uingizaji ulipoundwa, kwa hiyo wahusika askari waliundwa lakini hawakuwekwa kwenye kundi ambamo askari wanachaguliwa. Panga uingizaji tena ukitaja kundi, jambo linaloruhusu utekelezaji kuwaongeza, au kwenye usimamizi wa Django fungua **Patrol configuration › member subject groups**, chagua au unda kundi, kisha ongeza wahusika.

### Ongeza wahusika kwenye kundi la wahusika {#finding-permission_subject_group}

Kundi la orodha ya askari lipo lakini mtumiaji wa tovuti hawezi kubadilisha uanachama wa makundi ya wahusika. Mpe mtumiaji ruhusa hiyo kisha bonyeza **Endelea**, au ongeza wahusika kwenye kundi wewe mwenyewe kwenye **Django admin › Subject groups**. Jina la kundi linaonyeshwa pamoja na kitufe cha kunakili.

### Washa kipengele cha patrol_schemas {#finding-enable_patrol_schemas}

Tovuti imezima kipengele cha majaribio cha `patrol_schemas`, kwa hiyo haina vituo vya doria (legs), sehemu za jumla za kujaza za doria, timu wala orodha za kuingizia. Kwenye usimamizi wa Django, fungua **Preview features › patrol_schemas** na ukiwashe kwa mpangaji (tenant) huyu. Uliza EarthRanger Core kama ukurasa haupatikani. Kisha **Endelea**; sehemu za jumla za kujaza za doria zinaandikwa katika mzunguko unaofuata.

### Toa ruhusa: aina za doria {#finding-permission_patrol_types}

Mtumiaji wa tovuti hawezi kuunda wala kubadilisha aina za doria. Kwenye usimamizi wa Django, fungua **Users › the user** (mtumiaji husika) na uongeze `activity | patrol type | Can add/change patrol type`. Kisha **Endelea**.

### Toa ruhusa: sehemu za jumla za kujaza za doria {#finding-permission_segment_schema}

Mtumiaji wa tovuti hawezi kuandika sehemu za jumla za kujaza za doria (skima ya kipande). Ongeza `activity | segment type | Can change segment type`; kwa sasa hilo linahitaji mtumiaji mkuu (superuser). Kisha **Endelea**.

### Toa ruhusa: wahusika {#finding-permission_subjects}

Mtumiaji wa tovuti hawezi kuona, kuongeza wala kubadilisha wahusika, kwa hiyo wahusika askari hawakuweza kuundwa wala kupatikana. Ongeza `observations | subject | Can view/add/change subject`. Kisha **Endelea**.

### Toa ruhusa: usanidi wa doria {#finding-permission_patrol_config}

Mtumiaji wa tovuti hawezi kusoma usanidi wa doria, ambao hutumika kukagua timu na orodha za askari. Ongeza `activity | patrol | Can view patrol`. Kisha **Endelea**.

### Chagua aikoni kwa kila aina ya doria {#finding-patrol_type_icons}

Ni onyo, si kusimama. API haiwezi kuweka aikoni ya aina ya doria, kwa hiyo aina mpya zinaonyesha aikoni ya doria ya chaguo-msingi ya EarthRanger hadi uchague moja kwenye **EarthRanger admin › Patrol types**.

### Vipe majina vituo ambavyo SMART iliviacha bila majina {#finding-station_names}

Ni onyo, si kusimama. Baadhi ya vituo (stations) havina jina katika lugha yoyote ya SMART, kwa hiyo viliundwa kwa jina la muda kama `Unnamed station 1a2b3c4d`. Vipe majina kwenye SMART, kisha hamisha tena kutoka SMART (export) na upakie faili mpya, au badilisha jina la chaguo kwenye **Django admin › Choices** (sehemu ya `patrol_station`); utekelezaji wa baadaye unarudisha jina la muda hadi SMART iwe na jina.

## Ukaguzi wa awali

### Kanda ya saa ya kifurushi ilikisiwa {#finding-timezone}

Ni onyo. SMART haikurekodi kanda ya saa ya eneo la hifadhi, kwa hiyo utoaji wa data uliikisia kutokana na mahali vielekezi (waypoints) vilipo. Saa za doria na za vielelezo zinabadilishwa kwa kanda hiyo. Kama si sahihi, weka `SMART_ABLE_TIMEZONE` kwa ajili ya utoaji kisha endesha utoaji wa data (extract) wa seti hiyo upya; ukurasa wa mambo ya kipekee unaeleza jinsi kanda za saa zinavyoshughulikiwa.

### Lebo zinakosekana katika lugha iliyochaguliwa {#finding-language}

Ni onyo. Baadhi ya vipengele vya moduli data havina lebo katika lugha ambayo uingizaji uliundwa nayo, kwa hiyo vinatumia lugha ya chaguo-msingi ya kifurushi au lugha yoyote iliyo na lebo. Kichupo cha Data Model cha seti ya data kinaonyesha jinsi kila lugha ilivyokamilika; panga uingizaji tena kwa lugha iliyokamilika zaidi kama lebo ni muhimu.

### Siku za kituo cha doria zisizo na taarifa za saa {#finding-time_coverage}

Ni onyo, hakuna la kufanya. Baadhi ya siku za kituo cha doria (leg) hazina alama, hazina saa ya kuanza wala ya kumaliza, na hazina kielekezi (waypoint) chenye saa, kwa hiyo vipande vyake vinachukua siku nzima. Kila kipande cha namna hiyo kinarekodiwa na `time_source: date_only`.

### Ukaguzi mmoja wa awali haukuweza kufanyika {#finding-check_failed}

Mojawapo ya kaguzi ilitoa hitilafu kabla ya kuweza kutoa taarifa, kwa kawaida ni tatizo la muunganisho au la ruhusa na tovuti. Ujumbe unataja ukaguzi na hitilafu. Rekebisha chanzo, kisha bonyeza **Endelea**; ukaguzi wa awali unafanyika tena tangu mwanzo.

### Kipengele cha patrol_schemas kimezimwa {#finding-feature_flag}

Ni hali ileile ya *Washa kipengele cha patrol_schemas* hapo juu, ikionekana kutoka kwenye ukaguzi wa awali. Washa kipengele, kisha bonyeza **Endelea**.

### Mtumiaji wa tovuti hana ruhusa {#finding-permissions}

Tokeo linaorodhesha kila ruhusa ambayo uingizaji unahitaji na mtumiaji hana. Mpe mtumiaji ruhusa hizo kwenye **Django admin › Users › the user**, programu ya `activity`. Kuunda matukio kwenye kategoria ya matukio kunahitaji ruhusa ya kuunda ya kategoria hiyo, ambayo kwa kawaida inatolewa kupitia seti ya ruhusa. Kisha **Endelea**.

### Aina za doria zinakosekana au zimezimwa {#finding-patrol_types}

Maandalizi ya doria yanaunda aina ambazo vituo vya doria (legs) vinahitaji, kwa hiyo katika utekelezaji hili kwa kawaida linamaanisha aina fulani ilizimwa baadaye. Iwashe kwenye **EarthRanger admin › Patrol types**, au bonyeza **Endelea** ili kuyaacha maandalizi ya doria yaiunde upya. Katika mpango hili linatarajiwa: mpango hauandiki chochote, na tokeo linawekwa alama kuwa ni kitu ambacho utekelezaji utakiunda.

### Sehemu za jumla za kujaza za doria zinakosekana au zimeondolewa matumizi {#finding-segment_schema}

Maandalizi ya doria yanaandika sehemu hizi. Kama msimamizi aliiondoa mojawapo matumizi (deprecated) kwa makusudi, irudishe kwenye kitengeneza fomu za doria; vinginevyo bonyeza **Endelea**. Katika mpango hili linatarajiwa.

### Machaguo yanayotumiwa na doria yanakosekana au yamezimwa {#finding-choices}

Ni onyo. Baadhi ya machaguo ya orodha yanayotumiwa na doria hayapo kwenye tovuti au yalizimwa, kwa hiyo sehemu hizo zingehifadhiwa bila ingizo linalolingana. Maandalizi ya doria yanayaunda; chaguo ambalo msimamizi alilizima linaweza kuwashwa tena kwenye **Django admin › Choices**.

### Wanachama wa doria hawawezi kuwekwa kwenye kipande {#finding-subjects}

Wahusika askari wa wanachama hawa hawapo, au hawamo kwenye kundi lililoorodheshwa chini ya **Patrol configuration › members**. Maandalizi ya doria yanawaunda na, kama kundi la orodha ya askari lilitajwa, yanawaongeza humo. Vinginevyo waongeze kwenye kundi la namna hiyo kwenye **Django admin › Subject groups**. Katika mpango hili linatarajiwa.

### Wanachama wa doria si amilifu {#finding-inactive_members}

Ni onyo, hakuna la kufanya. EarthRanger inakubali wanachama amilifu (active) tu kwenye kipande, kwa hiyo uingizaji unawarudisha wahusika hawa kuwa amilifu kwa muda wa utekelezaji, kisha unawafanya wasiwe amilifu tena unapomalizika. Daftari la kumbukumbu linaliandika.

### Timu za doria zinakosekana au zimezimwa {#finding-teams}

Ni hali ileile ya *Unda timu ya doria* hapo juu: kila timu iliyotajwa lazima iwepo, iwe amilifu, na iwe na jina hilohilo la kuonyeshwa, chini ya **Patrol configuration › Teams**. Kuna ingizo moja kwa kila timu, pamoja na kitufe cha kunakili.

### Aina za matukio {#finding-event_types}

Kategoria za SMART zenye vielelezo zinahitaji aina ya tukio iliyo amilifu kwenye tovuti. Ujumbe unaeleza ni hali ipi inayohusika:

- **Hakuna aina ya tukio iliyo amilifu**: moduli data haijatumwa chini ya kategoria ya matukio ambayo uingizaji huu unaitumia. Katika mpango hili linatarajiwa na linawekwa alama kuwa ni kitu ambacho utekelezaji utakiunda. Katika utekelezaji, kagua kategoria ya matukio: kama utumaji wa awali ulitumia kitambulisho tofauti, panga uingizaji tena kwa kitambulisho hicho.
- **Inalingana na aina zaidi ya moja ya tukio**: tovuti ina utumaji kadhaa wa moduli data, chini ya kategoria tofauti za matukio, wenye majina yaleyale ya aina. Panga uingizaji tena kwa kategoria ya matukio ya utumaji unaotaka kuutumia.
- **Inaelekea kwenye aina ya tukio isiyo amilifu**: ni onyo. Kategoria ni kategoria mzazi ya SMART au iliacha kutumika; matukio yake yanaingizwa kwa kutumia aina isiyo amilifu, ambayo EarthRanger haiitoi kwa ripoti mpya. Washa aina hiyo kwenye **EarthRanger admin › Event types** kama askari wanapaswa kuendelea kuitumia.
- **Ipo tu kama vibadala (variants) vya moduli inayosanidika**: kategoria hizo zina aina moja ya tukio kwa kila fomu, na uingizaji bado hauwezi kujua kielelezo ni cha kibadala kipi. Doria hizo bado haziwezi kuingizwa; inahitajika ulinganisho wa vibadala, ambayo ni kazi inayosubiri kwenye er-smart-sync.

### Hakuna aina ya tukio ya mkusanyiko {#finding-collection_type}

Ni onyo. Baadhi ya vielekezi (waypoints) vina vielelezo kadhaa, na tovuti haina aina ya tukio ya `incident_collection` iliyo amilifu ya kuviweka pamoja, kwa hiyo matukio yake yanaingizwa bila kuwekwa pamoja. Ongeza au washa aina hiyo kwenye **EarthRanger admin › Event types** ili kuyaweka pamoja.

### Vituo vya doria vyenye tarehe bandia ya 1970 au vinavyochukua zaidi ya mwaka {#finding-leg_span}

Ni onyo, hakuna la kufanya. SMART inahifadhi baadhi ya tarehe za kituo cha doria (leg) kama tarehe bandia; uingizaji unabakiza tu siku za kituo zenye alama au kielekezi (waypoint). Ili kusahihisha tarehe, rekebisha kituo cha doria kwenye SMART, kisha hamisha tena kutoka SMART (export) na upakie faili mpya.

### Vielelezo ambavyo haiwezekani kusema nani aliviripoti {#finding-observers}

Ni onyo. Kila tukio lililoingizwa linamtaja aliyeliripoti: mhusika wa mtazamaji wa SMART, au, mtu huyo asipokuwa na mhusika kwenye tovuti, kiongozi wa kituo cha doria (leg), la sivyo mwanachama wake wa kwanza. Vielelezo vilivyoorodheshwa havina yeyote kati ya hao, kwa hiyo matukio yake hayana aliyeripoti. Hakuna la kufanya isipokuwa kama ni muhimu: mpe mtazamaji rekodi ya mfanyakazi kwenye SMART, kisha hamisha tena kutoka SMART (export) na upakie faili mpya. Mpango unaorodhesha tu vielelezo ambavyo wahusika wa utekelezaji wenyewe hawawezi kuvitatua.

### Utoaji wa data ulirekodi maonyo {#finding-bundle_warnings}

Ni onyo. smart-able iliandika mambo kuhusu data ilipoandika kifurushi. Yameorodheshwa kwenye faili ya maelezo (manifest) ya kifurushi na kuelezwa katika *SMART data quirks* (mambo ya kipekee ya data za SMART, kwa Kiingereza).

## Uingizaji (Import)

### Doria zilishindwa kuingizwa {#finding-patrols_failed}

Kila doria iliyoshindwa inaorodheshwa pamoja na hitilafu yake. Hitilafu nyingi zinataja kitu kinachokosekana kwenye tovuti: timu, mhusika, aina ya tukio. Rekebisha hayo, kisha bonyeza **Endelea**; ni doria zilizoshindwa tu zinazojaribiwa tena. `500` kwenye kitambulisho cha doria ambacho tayari kipo kwenye tovuti ni EarthRanger ikikataa nakala rudufu; jaribio jipya linasoma doria iliyopo na kuendelea.

### Tokeni ya tovuti haifanyi kazi tena {#finding-site_token_rejected}

Tovuti ilikataa tokeni, kwa hiyo hakuna kilichoandikwa. Ondoa tovuti, isajili upya kwa tokeni inayofanya kazi, kisha anzisha uingizaji mpya.

### Uingizaji huu unabadilisha kile ambacho tovuti tayari inacho {#finding-shared_set_changes}

Mpango umekuta aina za matukio za uingizaji huu tayari zipo kwenye tovuti, na moduli ya eneo hili la hifadhi inatofautiana nazo: ungebadilisha aina za matukio zilizoorodheshwa, au kuongeza machaguo ya orodha. Huenda maeneo mengine ya hifadhi yaliyoingizwa kwenye tovuti yanazishiriki. Kuendesha uingizaji kunaipa kila aina ya tukio iliyoorodheshwa sehemu za kujaza na jina la eneo hili, na kuongeza machaguo; hakuzimi chochote. Ikiwa tofauti hiyo inatarajiwa, endesha uingizaji. Ili kutenga moduli ya eneo hili, tengeneza mpango mpya na uupe jina jingine la kundi la aina za matukio.

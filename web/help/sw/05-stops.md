# Uingizaji unaposimama

Utekelezaji unasimama pale ambapo tovuti inahitaji jambo ambalo API haiwezi kulifanya, au pale ambapo tovuti haiko tayari kwa doria. Kila tokeo kwenye ukurasa wa uingizaji linataja la kufanya; maelezo yaliyo hapa yanatoa agizo lilelile kwa nafasi zaidi. Thamani ambazo tokeo linazionyesha pamoja na kitufe cha kunakili ni kamili: EarthRanger inazilinganisha kwa jina.

Majina ya menyu za usimamizi wa EarthRanger yanatolewa kwa Kiingereza, jinsi unavyoyaonyesha.

Baada ya kurekebisha tovuti, bonyeza **Continue** (endelea). Utekelezaji unarudia hatua za mwanzo, jambo ambalo ni la haraka, kisha unaendelea.

## Mpangilio wa doria (Patrol setup)

### Unda timu ya doria {#finding-team}

Doria za SMART zinataja timu; API ya EarthRanger haiwezi kuunda timu. Kwenye usimamizi wa Django, fungua **Patrol configuration › Teams** na uongeze timu ambayo sehemu yake ya *display* ni jina la timu lililoonyeshwa, kama lilivyo hasa. Tokeo linaorodhesha wanachama wa timu kwenye SMART, kwa taarifa yako; uingizaji unaitambua timu kwa jina lake tu. Kuna ingizo moja kwa kila timu inayokosekana; ziunde zote, kisha Continue.

### Waweke askari kwenye kundi la wahusika la orodha ya askari {#finding-roster_group}

Hakuna kundi la orodha ya askari lililotajwa uingizaji ulipoundwa, kwa hiyo wahusika askari waliundwa lakini hawakuwekwa kwenye kundi ambamo askari wanachaguliwa. Panga uingizaji tena ukitaja kundi, jambo linaloruhusu utekelezaji kuwaongeza, au kwenye usimamizi wa Django fungua **Patrol configuration › member subject groups**, chagua au unda kundi, kisha ongeza wahusika.

### Ongeza wahusika kwenye kundi la wahusika {#finding-permission_subject_group}

Kundi la orodha ya askari lipo lakini mtumiaji wa tovuti hawezi kubadilisha uanachama wa makundi ya wahusika. Mpe mtumiaji ruhusa hiyo kisha Continue, au ongeza wahusika kwenye kundi wewe mwenyewe kwenye **Django admin › Subject groups**. Jina la kundi linaonyeshwa pamoja na kitufe cha kunakili.

### Washa kipengele cha patrol_schemas {#finding-enable_patrol_schemas}

Tovuti imezima kipengele cha majaribio cha `patrol_schemas`, kwa hiyo haina vituo vya doria (legs), sehemu za jumla za doria, timu wala orodha za kuingizia. Kwenye usimamizi wa Django, fungua **Preview features › patrol_schemas** na ukiwashe kwa mpangaji (tenant) huyu. Uliza EarthRanger Core kama ukurasa haupatikani. Kisha Continue; sehemu za jumla za doria zinaandikwa katika mzunguko unaofuata.

### Toa ruhusa: aina za doria {#finding-permission_patrol_types}

Mtumiaji wa tovuti hawezi kuunda wala kubadilisha aina za doria. Kwenye usimamizi wa Django, fungua **Users › the user** (mtumiaji husika) na uongeze `activity | patrol type | Can add/change patrol type`. Kisha Continue.

### Toa ruhusa: sehemu za jumla za doria {#finding-permission_segment_schema}

Mtumiaji wa tovuti hawezi kuandika sehemu za jumla za doria (skima ya kipande). Ongeza `activity | segment type | Can change segment type`; kwa sasa hilo linahitaji mtumiaji mkuu (superuser). Kisha Continue.

### Toa ruhusa: wahusika {#finding-permission_subjects}

Mtumiaji wa tovuti hawezi kuona, kuongeza wala kubadilisha wahusika, kwa hiyo wahusika askari hawakuweza kuundwa wala kupatikana. Ongeza `observations | subject | Can view/add/change subject`. Kisha Continue.

### Toa ruhusa: mpangilio wa doria {#finding-permission_patrol_config}

Mtumiaji wa tovuti hawezi kusoma mpangilio wa doria, ambao timu na orodha zinakaguliwa dhidi yake. Ongeza `activity | patrol | Can view patrol`. Kisha Continue.

### Chagua aikoni kwa kila aina ya doria {#finding-patrol_type_icons}

Ni onyo, si kusimama. API haiwezi kuweka aikoni ya aina ya doria, kwa hiyo aina mpya zinaonyesha aikoni ya doria ya chaguo-msingi ya EarthRanger hadi uchague moja kwenye **EarthRanger admin › Patrol types**.

### Vipe majina vituo ambavyo SMART iliviacha bila majina {#finding-station_names}

Ni onyo, si kusimama. Baadhi ya vituo (stations) havina jina katika lugha yoyote ya SMART, kwa hiyo viliundwa kwa jina la muda kama `Unnamed station 1a2b3c4d`. Vipe majina kwenye SMART kisha hamisha tena, au badilisha jina la chaguo kwenye **Django admin › Choices** (sehemu ya `patrol_station`); utekelezaji wa baadaye unarudisha jina la muda hadi SMART iwe na jina.

## Ukaguzi wa awali (Preflight)

### Kanda ya saa ya kifurushi ilikisiwa {#finding-timezone}

Ni onyo. SMART haikurekodi kanda ya saa ya eneo la hifadhi, kwa hiyo utoaji wa data uliikisia kutokana na mahali vielekezi (waypoints) vilipo. Saa za doria na za vielelezo zinabadilishwa kwa kanda hiyo. Kama si sahihi, weka `SMART_ABLE_TIMEZONE` kwa ajili ya utoaji kisha toa data za seti hiyo tena; ukurasa wa mambo ya kipekee unaeleza jinsi kanda za saa zinavyoshughulikiwa.

### Lebo zinakosekana katika lugha iliyochaguliwa {#finding-language}

Ni onyo. Baadhi ya vipengele vya moduli data havina lebo katika lugha ambayo uingizaji uliundwa nayo, kwa hiyo vinatumia lugha ya chaguo-msingi ya kifurushi au lugha yoyote iliyo na lebo. Kichupo cha Data Model cha seti ya data kinaonyesha jinsi kila lugha ilivyokamilika; panga uingizaji tena kwa lugha iliyokamilika zaidi kama lebo ni muhimu.

### Siku za kituo cha doria zisizo na taarifa za saa {#finding-time_coverage}

Ni onyo, hakuna la kufanya. Baadhi ya siku za kituo cha doria (leg) hazina alama, hazina saa ya kuanza wala ya kumaliza, na hazina kielekezi (waypoint) chenye saa, kwa hiyo vipande vyake vinachukua siku nzima. Kila kipande cha namna hiyo kinarekodiwa na `time_source: date_only`.

### Ukaguzi mmoja wa awali haukuweza kufanyika {#finding-check_failed}

Mojawapo ya kaguzi ilitoa hitilafu kabla ya kuweza kutoa taarifa, kwa kawaida ni tatizo la muunganisho au la ruhusa na tovuti. Ujumbe unataja ukaguzi na hitilafu. Rekebisha chanzo, kisha Continue; ukaguzi wa awali unafanyika tena tangu mwanzo.

### Kipengele cha patrol_schemas kimezimwa {#finding-feature_flag}

Ni hali ileile ya *Washa kipengele cha patrol_schemas* hapo juu, ikionekana kutoka kwenye ukaguzi wa awali. Washa kipengele, kisha Continue.

### Mtumiaji wa tovuti hana ruhusa {#finding-permissions}

Tokeo linaorodhesha kila ruhusa ambayo uingizaji unahitaji na mtumiaji hana. Zitoe kwenye **Django admin › Users › the user**, programu ya `activity`. Kuunda matukio kwenye kundi kunahitaji ruhusa ya kuunda ya kundi hilo, ambayo kwa kawaida inatolewa kupitia seti ya ruhusa. Kisha Continue.

### Aina za doria zinakosekana au zimezimwa {#finding-patrol_types}

Mpangilio wa doria unaunda aina ambazo vituo vya doria (legs) vinahitaji, kwa hiyo katika utekelezaji hili kwa kawaida linamaanisha aina fulani ilizimwa baadaye. Iwashe kwenye **EarthRanger admin › Patrol types**, au Continue ili kuuacha mpangilio wa doria uiunde upya. Katika mpango hili linatarajiwa: mpango hauandiki chochote, na tokeo linawekwa alama kuwa ni kitu ambacho utekelezaji utakiunda.

### Sehemu za jumla za doria zinakosekana au zimepitwa na wakati {#finding-segment_schema}

Mpangilio wa doria unaandika sehemu hizi. Kama msimamizi aliifanya mojawapo ipitwe na wakati kwa makusudi, irudishe kwenye kitengeneza fomu za doria; vinginevyo Continue. Katika mpango hili linatarajiwa.

### Machaguo yanayotumiwa na doria yanakosekana au yamezimwa {#finding-choices}

Ni onyo. Baadhi ya machaguo ya orodha yanayotumiwa na doria hayapo kwenye tovuti au yalizimwa, kwa hiyo sehemu hizo zingehifadhiwa bila ingizo linalolingana. Mpangilio wa doria unayaunda; chaguo ambalo msimamizi alilizima linaweza kuwashwa tena kwenye **Django admin › Choices**.

### Wanachama wa doria hawawezi kuwekwa kwenye kipande {#finding-subjects}

Wahusika askari wa wanachama hawa hawapo, au hawamo kwenye kundi lililoorodheshwa chini ya **Patrol configuration › members**. Mpangilio wa doria unawaunda na, kama kundi la orodha ya askari lilitajwa, unawaongeza humo. Vinginevyo waongeze kwenye kundi la namna hiyo kwenye **Django admin › Subject groups**. Katika mpango hili linatarajiwa.

### Wanachama wa doria wamestaafishwa {#finding-inactive_members}

Ni onyo, hakuna la kufanya. EarthRanger inakubali wanachama walio hai tu kwenye kipande, kwa hiyo uingizaji unawawasha tena wahusika hawa kwa ajili ya utekelezaji na kuwastaafisha tena unapomalizika. Daftari la kumbukumbu linaliandika.

### Timu za doria zinakosekana au zimezimwa {#finding-teams}

Ni hali ileile ya *Unda timu ya doria* hapo juu: kila timu iliyotajwa lazima iwepo, iwe hai, na iwe na jina hilohilo la kuonyeshwa, chini ya **Patrol configuration › Teams**. Kuna ingizo moja kwa kila timu, pamoja na kitufe cha kunakili.

### Aina za matukio {#finding-event_types}

Kategoria za SMART zilizoonekana zinahitaji aina ya tukio iliyo hai kwenye tovuti. Ujumbe unaeleza ni hali ipi inayohusika:

- **No active event type** (hakuna aina ya tukio iliyo hai): moduli data haijatumwa chini ya kundi la matukio ambalo uingizaji huu unalitumia. Katika mpango hili linatarajiwa na linawekwa alama kuwa ni kitu ambacho utekelezaji utakiunda. Katika utekelezaji, kagua kundi la matukio: kama utumaji wa awali ulitumia kitambulisho tofauti, panga uingizaji tena kwa kitambulisho hicho.
- **Match more than one event type** (inalingana na aina zaidi ya moja ya tukio): tovuti ina utumaji kadhaa wa moduli data, chini ya makundi tofauti, wenye majina yaleyale ya aina. Panga uingizaji tena kwa kundi la matukio la utumaji unaotaka kuingiza dhidi yake.
- **Map to an inactive event type** (inaelekea kwenye aina ya tukio isiyo hai): ni onyo. Kategoria ni kategoria mzazi ya SMART au ilistaafishwa; matukio yake yanaingizwa dhidi ya aina isiyo hai, ambayo EarthRanger haiitoi kwa ripoti mpya. Washa aina hiyo kwenye **EarthRanger admin › Event types** kama askari wanapaswa kuendelea kuitumia.
- **Exist only as configurable model variants** (zipo tu kama matoleo ya modeli inayoweza kusanidiwa): kategoria hizo zina aina moja ya tukio kwa kila fomu, na uingizaji bado hauwezi kujua kielelezo ni cha toleo lipi. Doria hizo bado haziwezi kuingizwa; inahitajika ramani ya matoleo, ambayo ni kazi inayosubiri kwenye er-smart-sync.

### Hakuna aina ya tukio ya mkusanyiko {#finding-collection_type}

Ni onyo. Baadhi ya vielekezi (waypoints) vina vielelezo kadhaa, na tovuti haina aina ya tukio ya `incident_collection` iliyo hai ya kuviweka pamoja, kwa hiyo matukio yake yanaingizwa bila kuwekwa pamoja. Ongeza au washa aina hiyo kwenye **EarthRanger admin › Event types** ili kuyaweka pamoja.

### Vituo vya doria vyenye tarehe ya muda ya 1970 au vinavyochukua zaidi ya mwaka {#finding-leg_span}

Ni onyo, hakuna la kufanya. SMART inahifadhi baadhi ya tarehe za kituo cha doria (leg) kama tarehe ya muda; uingizaji unabakiza tu siku za kituo zenye alama au kielekezi (waypoint). Ili kusahihisha tarehe, rekebisha kituo cha doria kwenye SMART kisha hamisha tena.

### Vielelezo ambavyo haiwezekani kusema nani aliviripoti {#finding-observers}

Ni onyo. Kila tukio lililoingizwa linamtaja aliyeliripoti: mhusika wa mtazamaji wa SMART, au, mtu huyo asipokuwa na mhusika kwenye tovuti, kiongozi wa kituo cha doria (leg), la sivyo mwanachama wake wa kwanza. Vielelezo vilivyoorodheshwa havina yeyote kati ya hao, kwa hiyo matukio yake hayana aliyeripoti. Hakuna la kufanya isipokuwa kama ni muhimu: mpe mtazamaji rekodi ya mfanyakazi kwenye SMART kisha hamisha tena. Mpango unaorodhesha tu vielelezo ambavyo wahusika wa utekelezaji wenyewe hawawezi kuvitatua.

### Utoaji wa data ulirekodi maonyo {#finding-bundle_warnings}

Ni onyo. smart-able iliandika mambo kuhusu data ilipoandika kifurushi. Yameorodheshwa kwenye faili ya maelezo (manifest) ya kifurushi na kuelezwa katika *SMART data quirks* (mambo ya kipekee ya data za SMART, kwa Kiingereza).

## Uingizaji (Import)

### Doria zilishindwa kuingizwa {#finding-patrols_failed}

Kila doria iliyoshindwa inaorodheshwa pamoja na hitilafu yake. Hitilafu nyingi zinataja kitu kinachokosekana kwenye tovuti: timu, mhusika, aina ya tukio. Rekebisha hayo, kisha Continue; ni doria zilizoshindwa tu zinazojaribiwa tena. `500` kwenye kitambulisho cha doria ambacho tayari kipo kwenye tovuti ni EarthRanger ikikataa nakala rudufu; jaribio jipya linasoma doria iliyopo na kuendelea.

### Tokeni ya tovuti haifanyi kazi tena {#finding-site_token_rejected}

Tovuti ilikataa tokeni, kwa hiyo hakuna kilichoandikwa. Ondoa tovuti, isajili upya kwa tokeni inayofanya kazi, kisha anzisha uingizaji mpya.

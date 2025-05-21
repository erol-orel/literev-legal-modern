Release Notes
---


## [0.12.0](https://github.com/thegraphnetwork-literev/literev-legal/compare/0.11.0...0.12.0) (2025-05-21)

### Features

* add confidence score workflow for rag answers ([#240](https://github.com/thegraphnetwork-literev/literev-legal/issues/240)) ([c8edb03](https://github.com/thegraphnetwork-literev/literev-legal/commit/c8edb03671a1fd586cefd241bf6c8f5acb008e17))
* add django command to count tokens ([#219](https://github.com/thegraphnetwork-literev/literev-legal/issues/219)) ([892e6a1](https://github.com/thegraphnetwork-literev/literev-legal/commit/892e6a143d4b78985b2290aad2c7f341ca407cac))
* add extended citation context for rag answer scoring ([#260](https://github.com/thegraphnetwork-literev/literev-legal/issues/260)) ([fb6800a](https://github.com/thegraphnetwork-literev/literev-legal/commit/fb6800ae0db7fe750a964c3191aad2426990b125))
* add faithfulness ragas score ([#290](https://github.com/thegraphnetwork-literev/literev-legal/issues/290)) ([00865a8](https://github.com/thegraphnetwork-literev/literev-legal/commit/00865a817f6c6f4763daf4ca3eb7ab2db31eedec))
* add faithfulness score workflow ([#241](https://github.com/thegraphnetwork-literev/literev-legal/issues/241)) ([c533b57](https://github.com/thegraphnetwork-literev/literev-legal/commit/c533b57568362f6f239f053c1fbfa879cad332e8))
* add hactar rago ([#271](https://github.com/thegraphnetwork-literev/literev-legal/issues/271)) ([1649326](https://github.com/thegraphnetwork-literev/literev-legal/commit/1649326c71bc79f864319779685cc6e8adc747b4))
* add minor features ([#216](https://github.com/thegraphnetwork-literev/literev-legal/issues/216)) ([57eba88](https://github.com/thegraphnetwork-literev/literev-legal/commit/57eba88a2a1e1c794b1c8517f1149653d46a37fe))
* add nlp workflow ([#203](https://github.com/thegraphnetwork-literev/literev-legal/issues/203)) ([a4e51bd](https://github.com/thegraphnetwork-literev/literev-legal/commit/a4e51bde40e9cd1fb8a3de731133bfd8a1e6c025))
* add selectors yes maybe and no in table select page ([#185](https://github.com/thegraphnetwork-literev/literev-legal/issues/185)) ([bac3aa8](https://github.com/thegraphnetwork-literev/literev-legal/commit/bac3aa8fa681ed8c2087ad317cf6856dd817daaa))
* add sentry for errors management ([#270](https://github.com/thegraphnetwork-literev/literev-legal/issues/270)) ([3356112](https://github.com/thegraphnetwork-literev/literev-legal/commit/335611212d97f0ae772b0e5063fa3e1e1c362854))
* add sorting rag answer ([#244](https://github.com/thegraphnetwork-literev/literev-legal/issues/244)) ([060966b](https://github.com/thegraphnetwork-literev/literev-legal/commit/060966b69309772ade1d12fab49901e489ffc329))
* Add support for caching ([#215](https://github.com/thegraphnetwork-literev/literev-legal/issues/215)) ([60b8ed1](https://github.com/thegraphnetwork-literev/literev-legal/commit/60b8ed1ceb0b7f0ef62ed616a1ffebfd3c3a2165))
* add valid and total document counters to RAG history table ([#284](https://github.com/thegraphnetwork-literev/literev-legal/issues/284)) ([e8c0bf5](https://github.com/thegraphnetwork-literev/literev-legal/commit/e8c0bf588134b4d18f60874162b14bf3fdfccb6b))
* **api:** add initial implementation for natural language to boolean query translation ([#202](https://github.com/thegraphnetwork-literev/literev-legal/issues/202)) ([abd9ee6](https://github.com/thegraphnetwork-literev/literev-legal/commit/abd9ee6e07e53a3d17ba41068f11f736fff61915))
* **ci:** Update workflow to run in self-hosted ([#261](https://github.com/thegraphnetwork-literev/literev-legal/issues/261)) ([4f70ba8](https://github.com/thegraphnetwork-literev/literev-legal/commit/4f70ba86482bff65cd23c2a8833601a412b1fbd2))
* **elasticsearch:** Improve Elasticsearch Docker Compose for Production Multi‑Node Cluster ([#264](https://github.com/thegraphnetwork-literev/literev-legal/issues/264)) ([19aaba4](https://github.com/thegraphnetwork-literev/literev-legal/commit/19aaba4c953086ebc5bf1f3be7b6cce43d5022f7))
* **elasticsearch:** Set unassigned replicas in a single-node cluster ([#253](https://github.com/thegraphnetwork-literev/literev-legal/issues/253)) ([7b8e7f6](https://github.com/thegraphnetwork-literev/literev-legal/commit/7b8e7f6293d02002c780e9f38908494c22fbe34c))
* enable processing projects with documents greater than zero  ([#278](https://github.com/thegraphnetwork-literev/literev-legal/issues/278)) ([ee8284f](https://github.com/thegraphnetwork-literev/literev-legal/commit/ee8284f34ebf5f16d5549db1ea93a361a3712e79))
* Improve 'count-tokens' script ([#220](https://github.com/thegraphnetwork-literev/literev-legal/issues/220)) ([32362d2](https://github.com/thegraphnetwork-literev/literev-legal/commit/32362d2ce5cd58cbcb8a40e5744aa3f4221d2340))
* **rag-api:** Add RAG status display in history table via REST API ([#288](https://github.com/thegraphnetwork-literev/literev-legal/issues/288)) ([34e8d26](https://github.com/thegraphnetwork-literev/literev-legal/commit/34e8d26d4b5217cb6ec32d277125730d3b8216ad))
* **rag:** add document-level caching using query and document ID ([#297](https://github.com/thegraphnetwork-literev/literev-legal/issues/297)) ([30715ae](https://github.com/thegraphnetwork-literev/literev-legal/commit/30715aeec1b1d655cee18f74726fb5d8c93446a3))
* **rag:** Implement delete button for removing RAG history entries ([#222](https://github.com/thegraphnetwork-literev/literev-legal/issues/222)) ([5908e38](https://github.com/thegraphnetwork-literev/literev-legal/commit/5908e3840fdcd916b56c997463ea72787ca9a24b))
* **rag:** Implement historical table with document rendering support ([#214](https://github.com/thegraphnetwork-literev/literev-legal/issues/214)) ([8b402bb](https://github.com/thegraphnetwork-literev/literev-legal/commit/8b402bbf767812c43a66a62d0caef139065b4414))
* **rag:** Implement sorting of RAG answers ([#196](https://github.com/thegraphnetwork-literev/literev-legal/issues/196)) ([69bf75c](https://github.com/thegraphnetwork-literev/literev-legal/commit/69bf75c926f62d942cd3de905f4e751f9c9ba283))
* **rag:** Implement statistics using RAG for bullet-points ([#254](https://github.com/thegraphnetwork-literev/literev-legal/issues/254)) ([6f11584](https://github.com/thegraphnetwork-literev/literev-legal/commit/6f115844be898ecd1de7139e578bc81843448d4a))
* **rag:** link procedure type tags in general summary bullet points ([#247](https://github.com/thegraphnetwork-literev/literev-legal/issues/247)) ([7e9fcce](https://github.com/thegraphnetwork-literev/literev-legal/commit/7e9fcce289b28bb08ea46e2a052b3be1cc312066))
* **rag:** refine prompt for consideration eval ([#276](https://github.com/thegraphnetwork-literev/literev-legal/issues/276)) ([243a937](https://github.com/thegraphnetwork-literev/literev-legal/commit/243a937ab12eb0bbb38b0705dce98ad977cd928f))
* **research-NLQ:** Improve prompt template rules and add validation tests ([#234](https://github.com/thegraphnetwork-literev/literev-legal/issues/234)) ([daf51b9](https://github.com/thegraphnetwork-literev/literev-legal/commit/daf51b9ad75794c5f166f8c9c83c0c178a7e8002))
* **tableselect:** Set es_score as the default sorting order ([#184](https://github.com/thegraphnetwork-literev/literev-legal/issues/184)) ([ee38b60](https://github.com/thegraphnetwork-literev/literev-legal/commit/ee38b60dd37c8fa3300359663ca084a231681251))

### Bug Fixes

* **docker-compose:** Optimize Elasticsearch memory settings and environment config ([#250](https://github.com/thegraphnetwork-literev/literev-legal/issues/250)) ([212b4b7](https://github.com/thegraphnetwork-literev/literev-legal/commit/212b4b756ade15275baebdf246fc76904c4e060f))
* document counter in views ([#282](https://github.com/thegraphnetwork-literev/literev-legal/issues/282)) ([f36eee8](https://github.com/thegraphnetwork-literev/literev-legal/commit/f36eee8277cfc19ebf753aab0027183a4bde0941))
* Fix RAG workflow after submitting a question ([#218](https://github.com/thegraphnetwork-literev/literev-legal/issues/218)) ([7fc8e46](https://github.com/thegraphnetwork-literev/literev-legal/commit/7fc8e463f938ee48496146ce1ddbbd08dc524560))
* **forms:** Resolve default date handling and persist selected sources ([#208](https://github.com/thegraphnetwork-literev/literev-legal/issues/208)) ([5f45817](https://github.com/thegraphnetwork-literev/literev-legal/commit/5f4581775e7eda6ce0dbb2a1dd145a14fa6115cf))
* Improve the RAG result ([#223](https://github.com/thegraphnetwork-literev/literev-legal/issues/223)) ([3a9a430](https://github.com/thegraphnetwork-literev/literev-legal/commit/3a9a4309dbd8cbbee25df288bc99e0bf02379cdb))
* Improve the results with spacy model large version ([#211](https://github.com/thegraphnetwork-literev/literev-legal/issues/211)) ([cd98410](https://github.com/thegraphnetwork-literev/literev-legal/commit/cd984105e25b0adc3601814e826ce7dd8820ec4b))
* **JS:** Improve scripts for tableselect page ([#226](https://github.com/thegraphnetwork-literev/literev-legal/issues/226)) ([54f178e](https://github.com/thegraphnetwork-literev/literev-legal/commit/54f178ede98691c4e0a7cd4e5486f00a29f71f36))
* load all results at once ([#248](https://github.com/thegraphnetwork-literev/literev-legal/issues/248)) ([3680e4a](https://github.com/thegraphnetwork-literev/literev-legal/commit/3680e4aa62f763d4a0e68382af2f84cbdb88d479))
* **rag:** ensure post-processing runs after early document limit ([#281](https://github.com/thegraphnetwork-literev/literev-legal/issues/281)) ([42ba952](https://github.com/thegraphnetwork-literev/literev-legal/commit/42ba9529c3ce0ea589d811904bea0569b3ba84c2))
* **rag:** limit initial RAG query to top 10 documents for new projects ([#293](https://github.com/thegraphnetwork-literev/literev-legal/issues/293)) ([99961d3](https://github.com/thegraphnetwork-literev/literev-legal/commit/99961d35a357838081669061105014b4ab480655))
* **rag:** restrict queryset to selected document_ids in evaluations ([#295](https://github.com/thegraphnetwork-literev/literev-legal/issues/295)) ([cc40d84](https://github.com/thegraphnetwork-literev/literev-legal/commit/cc40d84618807e0871a27ad878671fe124d88673))
* **rag:** safely compare confidence_score to avoid NoneType errors ([#277](https://github.com/thegraphnetwork-literev/literev-legal/issues/277)) ([638f1cb](https://github.com/thegraphnetwork-literev/literev-legal/commit/638f1cb9fbc86700ce2ba9be9edd2d5b77d23570))
* **rag:** update answer checks to use includes strings ([#228](https://github.com/thegraphnetwork-literev/literev-legal/issues/228)) ([31ee192](https://github.com/thegraphnetwork-literev/literev-legal/commit/31ee192492255d12e9782df3e701bab5dcdccdc1))
* solve ask question query ([#246](https://github.com/thegraphnetwork-literev/literev-legal/issues/246)) ([9c3411b](https://github.com/thegraphnetwork-literev/literev-legal/commit/9c3411b4e80cdaf3337e0774f46520f3adc1982b))
* solve bug check all buttons ([#267](https://github.com/thegraphnetwork-literev/literev-legal/issues/267)) ([28ab4ef](https://github.com/thegraphnetwork-literev/literev-legal/commit/28ab4ef8cd9ac10e1ec78cebe57673cdb329b22f))
* solve bug tfidfvectorizer stopwords ([#198](https://github.com/thegraphnetwork-literev/literev-legal/issues/198)) ([0813dc7](https://github.com/thegraphnetwork-literev/literev-legal/commit/0813dc75e6f1b332d2064d554f3fab47e4b74231))
* solve delete button bug ([#285](https://github.com/thegraphnetwork-literev/literev-legal/issues/285)) ([947d6d1](https://github.com/thegraphnetwork-literev/literev-legal/commit/947d6d17ff3e80878628d4c5434a9e0ec30a73cc))
* update tableselect post handler ([#199](https://github.com/thegraphnetwork-literev/literev-legal/issues/199)) ([a5207f6](https://github.com/thegraphnetwork-literev/literev-legal/commit/a5207f6a7c8a4f7397a3881c04abb3aeb1d95b57))

## [0.11.0](https://github.com/thegraphnetwork-literev/literev-legal/compare/0.10.0...0.11.0) (2024-12-19)

### Features

* add early results ([#178](https://github.com/thegraphnetwork-literev/literev-legal/issues/178)) ([7de8546](https://github.com/thegraphnetwork-literev/literev-legal/commit/7de85466dd9dd41df783785428dc65feb87ee3bb))
* **project-page:** Improve refinement filter  ([#179](https://github.com/thegraphnetwork-literev/literev-legal/issues/179)) ([763a934](https://github.com/thegraphnetwork-literev/literev-legal/commit/763a934755ab1824369ce3c68c6a1fad2060809b))
* **ui:** add 'See All Documents' button ([#177](https://github.com/thegraphnetwork-literev/literev-legal/issues/177)) ([2853dd8](https://github.com/thegraphnetwork-literev/literev-legal/commit/2853dd84d23b073d15c6a62e905f2e55335f3c61))

### Bug Fixes

* **plot:** hide tooltips for cluster number circles and improve circle rendering ([#172](https://github.com/thegraphnetwork-literev/literev-legal/issues/172)) ([91b0a9c](https://github.com/thegraphnetwork-literev/literev-legal/commit/91b0a9ce51cbbf35f216e10f4740831291e59744))
* **rag:** set temperature parameter to 0 in OpenAIGen ([#182](https://github.com/thegraphnetwork-literev/literev-legal/issues/182)) ([c992418](https://github.com/thegraphnetwork-literev/literev-legal/commit/c9924189ec26debf07ca3268e667ad50c583bbd3))
* **tableselect:** update tableupdate functions api ([#168](https://github.com/thegraphnetwork-literev/literev-legal/issues/168)) ([6adf0c4](https://github.com/thegraphnetwork-literev/literev-legal/commit/6adf0c4f086d07a4749984b1e6c29498dbc6a005))

## [0.10.0](https://github.com/thegraphnetwork-literev/literev-legal/compare/0.9.0...0.10.0) (2024-12-06)

### Features

* add refinement criteria in table select ([#159](https://github.com/thegraphnetwork-literev/literev-legal/issues/159)) ([662dfab](https://github.com/thegraphnetwork-literev/literev-legal/commit/662dfabcb761f732f7282b6282a6bbf8bc747845))
* add update projects workflow  ([#160](https://github.com/thegraphnetwork-literev/literev-legal/issues/160)) ([48451ea](https://github.com/thegraphnetwork-literev/literev-legal/commit/48451eaab5d9b69981788a7c58264dedc02030bd))
* **branding:** Add tagline and new LiteRev logo ([#156](https://github.com/thegraphnetwork-literev/literev-legal/issues/156)) ([ce0aa05](https://github.com/thegraphnetwork-literev/literev-legal/commit/ce0aa052235186823d93da1644aa876784c8f9d8))
* **django-template:** Refactor templates, enhance navigation, and implement team page prototype   ([#164](https://github.com/thegraphnetwork-literev/literev-legal/issues/164)) ([b61fa59](https://github.com/thegraphnetwork-literev/literev-legal/commit/b61fa59d03c1a9b09e8c291082a368615686fd80))
* **plot:** Display cluster numbers in black, bold text inside circles ([#158](https://github.com/thegraphnetwork-literev/literev-legal/issues/158)) ([d9446d0](https://github.com/thegraphnetwork-literev/literev-legal/commit/d9446d00370d0ed3efc43c2fef75a36e9b8bca04))

### Bug Fixes

* make compatible update workflow with old projects ([#162](https://github.com/thegraphnetwork-literev/literev-legal/issues/162)) ([4fbf6c0](https://github.com/thegraphnetwork-literev/literev-legal/commit/4fbf6c07e5ae5d5ff00088cbb6db0a423d061111))
* solve iteration bug ([#161](https://github.com/thegraphnetwork-literev/literev-legal/issues/161)) ([689d78a](https://github.com/thegraphnetwork-literev/literev-legal/commit/689d78a98e288a312bd516c81a83df53482dbb9b))

## [0.9.0](https://github.com/thegraphnetwork-literev/literev-legal/compare/0.8.1...0.9.0) (2024-11-26)

### Features

* **rag:** improve French response handling for unavailable content ([#154](https://github.com/thegraphnetwork-literev/literev-legal/issues/154)) ([514ddbe](https://github.com/thegraphnetwork-literev/literev-legal/commit/514ddbe302213f5d272a27fcb60b52731b81acf0))

## [0.8.1](https://github.com/thegraphnetwork-literev/literev-legal/compare/0.8.0...0.8.1) (2024-11-26)

### Bug Fixes

* Improve the RAG prompt ([#152](https://github.com/thegraphnetwork-literev/literev-legal/issues/152)) ([6caedb3](https://github.com/thegraphnetwork-literev/literev-legal/commit/6caedb3a6a4cf577bfb9156107c1c572b2433562))
* just show 10 keywords from topic ([#153](https://github.com/thegraphnetwork-literev/literev-legal/issues/153)) ([ee6913c](https://github.com/thegraphnetwork-literev/literev-legal/commit/ee6913cc168bbb00e8c060b8f73a0c59b8a0bb77))

## [0.8.0](https://github.com/thegraphnetwork-literev/literev-legal/compare/0.7.0...0.8.0) (2024-11-25)

### Features

* enable sharing projects to all users by id ([#136](https://github.com/thegraphnetwork-literev/literev-legal/issues/136)) ([5747fb3](https://github.com/thegraphnetwork-literev/literev-legal/commit/5747fb396db56c8ee2c22d45a8de10918a38dcf1))

## [0.7.0](https://github.com/thegraphnetwork-literev/literev-legal/compare/0.6.0...0.7.0) (2024-11-25)

### Features

* Improve Clustering Summary ([#145](https://github.com/thegraphnetwork-literev/literev-legal/issues/145)) ([ee2b3fe](https://github.com/thegraphnetwork-literev/literev-legal/commit/ee2b3febc04a90b46edde6d3f0d49638cb88a737))
* **rag:** Enhance RAG prompt template to handle closed questions ([#148](https://github.com/thegraphnetwork-literev/literev-legal/issues/148)) ([c6e7a12](https://github.com/thegraphnetwork-literev/literev-legal/commit/c6e7a1237c21c2884357dd3949c6eb4453c53824))

## [0.6.0](https://github.com/thegraphnetwork-literev/literev-legal/compare/0.5.0...0.6.0) (2024-11-22)

### Features

* add rag workflow ([#137](https://github.com/thegraphnetwork-literev/literev-legal/issues/137)) ([0aaedf9](https://github.com/thegraphnetwork-literev/literev-legal/commit/0aaedf90e6438e78e4068c69563a1693fb7153d9))
* **config:** Update Makim Tasks, Sugar Commands, and Development Dependencies   ([#131](https://github.com/thegraphnetwork-literev/literev-legal/issues/131)) ([9c0464d](https://github.com/thegraphnetwork-literev/literev-legal/commit/9c0464dde3afe6ec672b30d288f776a559d117dd))
* highlight keywords in tableselect page ([#127](https://github.com/thegraphnetwork-literev/literev-legal/issues/127)) ([e81fc8e](https://github.com/thegraphnetwork-literev/literev-legal/commit/e81fc8e69e12dc4a235c31d0c365d12593a422c2))
* **summary:** switch from gpt-3.5-turbo to gpt-4o-mini and refine prompt template ([#142](https://github.com/thegraphnetwork-literev/literev-legal/issues/142)) ([debc93a](https://github.com/thegraphnetwork-literev/literev-legal/commit/debc93a2d0d326064fd16236d4a7d0f3a665e29a))
* **ui:** implement color-coded topics and keyword highlights ([#139](https://github.com/thegraphnetwork-literev/literev-legal/issues/139)) ([6571996](https://github.com/thegraphnetwork-literev/literev-legal/commit/657199625ebfd605db75b793d19aa7e533088540))

### Bug Fixes

* solve refinement workflow and add minor changes ([#129](https://github.com/thegraphnetwork-literev/literev-legal/issues/129)) ([b27a778](https://github.com/thegraphnetwork-literev/literev-legal/commit/b27a778fdbb5816d8ca1e2372f0a7e585219dcec))
* solve summary color issues ([#126](https://github.com/thegraphnetwork-literev/literev-legal/issues/126)) ([98eb0e0](https://github.com/thegraphnetwork-literev/literev-legal/commit/98eb0e04e5703bc111f865dd4ece85bbb74c2cde))

## [0.5.0](https://github.com/thegraphnetwork-literev/literev-legal/compare/0.4.0...0.5.0) (2024-10-17)

### Features

* add elasticsearch scores to sort tableselect page ([#125](https://github.com/thegraphnetwork-literev/literev-legal/issues/125)) ([5ff7225](https://github.com/thegraphnetwork-literev/literev-legal/commit/5ff7225fb887edb2cb7efa719fb40f24ac539dec))
* **django-management:** Refactor ALL-CORPUS processing into standalone script with Makim task ([#120](https://github.com/thegraphnetwork-literev/literev-legal/issues/120)) ([33ca5af](https://github.com/thegraphnetwork-literev/literev-legal/commit/33ca5af9ea21cb225c11bce7e8ed966c31ebf43f))
* sort by keyword in query and show hdbscan scores in table select page ([#115](https://github.com/thegraphnetwork-literev/literev-legal/issues/115)) ([93d04c9](https://github.com/thegraphnetwork-literev/literev-legal/commit/93d04c9af7d89360aaa9ae1599a1f6b5159cb4b5))

### Bug Fixes

* allow permissions to first project ([#119](https://github.com/thegraphnetwork-literev/literev-legal/issues/119)) ([15008a9](https://github.com/thegraphnetwork-literev/literev-legal/commit/15008a902ccb0ee511f71322d63249ea9ca46356))

## [0.4.0](https://github.com/thegraphnetwork-literev/literev-legal/compare/0.3.0...0.4.0) (2024-10-09)

### Features

* add historical page ([#110](https://github.com/thegraphnetwork-literev/literev-legal/issues/110)) ([ec503d5](https://github.com/thegraphnetwork-literev/literev-legal/commit/ec503d5aad3c863b0b99152f12cd7c267238c1e4))
* Update collectors to support multiple data sources ([#114](https://github.com/thegraphnetwork-literev/literev-legal/issues/114)) ([fc64a2e](https://github.com/thegraphnetwork-literev/literev-legal/commit/fc64a2e8312273142ada57ab3b90cd2e0f34956b))

## [0.3.0](https://github.com/thegraphnetwork-literev/literev-legal/compare/0.2.0...0.3.0) (2024-10-03)

### Features

* add filter selector in graph result page ([#44](https://github.com/thegraphnetwork-literev/literev-legal/issues/44)) ([996772c](https://github.com/thegraphnetwork-literev/literev-legal/commit/996772c9d0023e218ae896b54bf24ec819084fbf))
* add html document content page ([#59](https://github.com/thegraphnetwork-literev/literev-legal/issues/59)) ([d9d6363](https://github.com/thegraphnetwork-literev/literev-legal/commit/d9d6363835f88194374b91b3b420428c3582970b))
* add project page with iteration and refinement features ([#108](https://github.com/thegraphnetwork-literev/literev-legal/issues/108)) ([a9ae1b4](https://github.com/thegraphnetwork-literev/literev-legal/commit/a9ae1b47de62226c8330969a4001bb784a03c8a9))
* add remove button for running projects in running page ([#81](https://github.com/thegraphnetwork-literev/literev-legal/issues/81)) ([49884da](https://github.com/thegraphnetwork-literev/literev-legal/commit/49884dac2b91c77eb385706687387721754f3293))
* add remove button in running page ([#65](https://github.com/thegraphnetwork-literev/literev-legal/issues/65)) ([dbbf8c8](https://github.com/thegraphnetwork-literev/literev-legal/commit/dbbf8c828ce8f87a74490a82ea9bbb81ecd10473))
* add summary auto generation ([#68](https://github.com/thegraphnetwork-literev/literev-legal/issues/68)) ([749ac1b](https://github.com/thegraphnetwork-literev/literev-legal/commit/749ac1bba36e7e6765ea64e6d4d367c7bc79c191))
* add table select page ([#46](https://github.com/thegraphnetwork-literev/literev-legal/issues/46)) ([2a03a56](https://github.com/thegraphnetwork-literev/literev-legal/commit/2a03a568b18f8ff70933f2e8b15630c96a56ba22))
* Add task to index data into Elasticsearch ([#60](https://github.com/thegraphnetwork-literev/literev-legal/issues/60)) ([01fc9fc](https://github.com/thegraphnetwork-literev/literev-legal/commit/01fc9fc5cf897502f7174538495b2b107cb56d0c))
* add user login ([#74](https://github.com/thegraphnetwork-literev/literev-legal/issues/74)) ([c03a0b4](https://github.com/thegraphnetwork-literev/literev-legal/commit/c03a0b4ae21ebfa3f05283c77a350cdf3f0b4363))
* **docker:** Enhancements for Elasticsearch integration and JSON data indexing ([#103](https://github.com/thegraphnetwork-literev/literev-legal/issues/103)) ([0c744f2](https://github.com/thegraphnetwork-literev/literev-legal/commit/0c744f2fb5a742497e47481970af1fedab46e720))
* enable filter by result and year in graph page ([#62](https://github.com/thegraphnetwork-literev/literev-legal/issues/62)) ([9dad7c5](https://github.com/thegraphnetwork-literev/literev-legal/commit/9dad7c51b28c6f083e23aa167532eaa621935746))
* enable openai summary generation ([#45](https://github.com/thegraphnetwork-literev/literev-legal/issues/45)) ([0a67379](https://github.com/thegraphnetwork-literev/literev-legal/commit/0a6737902df7f95a1dac1faabffc6e958e5dc087))
* Enhance Docker CPU Limits with env variables and DjangosScript improvements ([#53](https://github.com/thegraphnetwork-literev/literev-legal/issues/53)) ([73166f5](https://github.com/thegraphnetwork-literev/literev-legal/commit/73166f56df9abd84d62276ce3639d71020999b2f))
* **form:** Make Decision date explicit in the search form ([#100](https://github.com/thegraphnetwork-literev/literev-legal/issues/100)) ([8bc0281](https://github.com/thegraphnetwork-literev/literev-legal/commit/8bc0281769a952f962566829b912189545b8f558))
* Implement Celery for task management to replace existing Threading ([#49](https://github.com/thegraphnetwork-literev/literev-legal/issues/49)) ([7212af9](https://github.com/thegraphnetwork-literev/literev-legal/commit/7212af970cbf737065794c637d5a3088665677b3))
* Implement order by functionality in table selection ([#102](https://github.com/thegraphnetwork-literev/literev-legal/issues/102)) ([81051f9](https://github.com/thegraphnetwork-literev/literev-legal/commit/81051f9dd2cd899ab722c04a1c6d97016a5d6e37))
* **nginx:** implement configuration and add SSL certificates for production ([#77](https://github.com/thegraphnetwork-literev/literev-legal/issues/77)) ([d0fdb09](https://github.com/thegraphnetwork-literev/literev-legal/commit/d0fdb099f9cf63488b5fcf9087175829f21979a9))
* **refine-project:** Add descriptor filtering support ([#101](https://github.com/thegraphnetwork-literev/literev-legal/issues/101)) ([90cb755](https://github.com/thegraphnetwork-literev/literev-legal/commit/90cb7552971daa1b6841cf8c2129be84d6ae07f2))
* **refine-project:** Add support for filtering documents by year range ([#99](https://github.com/thegraphnetwork-literev/literev-legal/issues/99)) ([92b918f](https://github.com/thegraphnetwork-literev/literev-legal/commit/92b918f8ae031363aacbff5aae75857a06b94ee2))
* run clustering step outside container ([#47](https://github.com/thegraphnetwork-literev/literev-legal/issues/47)) ([ce664cb](https://github.com/thegraphnetwork-literev/literev-legal/commit/ce664cb91534d892a0442106cf765fc144dd446f))
* update select page ([#54](https://github.com/thegraphnetwork-literev/literev-legal/issues/54)) ([40addb5](https://github.com/thegraphnetwork-literev/literev-legal/commit/40addb5c7a8a611c96600c594024dc360972463d))

### Bug Fixes

* **docker:** update volume paths for LiteRev base image ([66fbe7d](https://github.com/thegraphnetwork-literev/literev-legal/commit/66fbe7d6b1db3364d83a7d809d4a6e56a472f544))
* fix bugs in exporting unclassified papers ([#63](https://github.com/thegraphnetwork-literev/literev-legal/issues/63)) ([a4f3ac4](https://github.com/thegraphnetwork-literev/literev-legal/commit/a4f3ac4c670209190e1c53d7adc25b9cb515888c))

## [0.2.0](https://github.com/thegraphnetwork-literev/literev-legal/compare/0.1.0...0.2.0) (2024-04-11)


### Features

* add temporary code to run on the whole corpus ([#26](https://github.com/thegraphnetwork-literev/literev-legal/issues/26)) ([c19f2d1](https://github.com/thegraphnetwork-literev/literev-legal/commit/c19f2d116ad451183db2e01a7e526d0484a0bf97))
* Enhanced data handling and storage for Metadata in Django database ([#37](https://github.com/thegraphnetwork-literev/literev-legal/issues/37)) ([b1973f8](https://github.com/thegraphnetwork-literev/literev-legal/commit/b1973f83229c4de96def2dfb55955e4c710869a4))
* Integrate connection URI for PostgreSQL database to connect optuna ([#30](https://github.com/thegraphnetwork-literev/literev-legal/issues/30)) ([82779bd](https://github.com/thegraphnetwork-literev/literev-legal/commit/82779bd743ee5213c666a95bdce89eb57173f3c9))


### Bug Fixes

* Add missing 'runs-on' property in release.yaml workflow ([#33](https://github.com/thegraphnetwork-literev/literev-legal/issues/33)) ([2d9be9b](https://github.com/thegraphnetwork-literev/literev-legal/commit/2d9be9b36ad48325f5f5c3551c948870d1b2327c))
* **docs:** Set path to environment file ([#27](https://github.com/thegraphnetwork-literev/literev-legal/issues/27)) ([385776b](https://github.com/thegraphnetwork-literev/literev-legal/commit/385776bd82ac75b7454eb44350ac15655c39d3a4))

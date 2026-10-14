import fs from 'node:fs/promises';
import path from 'node:path';
import {educationArticles} from '../src/education.js';
const base=(process.env.SITE_URL||'https://95.85.251.67').replace(/\/$/,'');
const escape=value=>String(value).replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const index=await fs.readFile('dist/index.html','utf8');
for(const [slug,article] of Object.entries(educationArticles)){
 const url=base+'/materials/'+slug;
 const image=base+(article.image||'/assets/arctic-coast.webp');
 const schema=JSON.stringify({'@context':'https://schema.org','@type':'Article',headline:article.title,description:article.intro,image,mainEntityOfPage:url,author:{'@type':'Organization',name:'asa team'}}).replace(/</g,'\\u003c');
 const content=`<div id="app"><main id="content" class="shell"><article class="reading-page"><a href="/materials">Все материалы</a><h1>${escape(article.title)}</h1><p class="reading-lead">${escape(article.intro)}</p><figure class="article-hero"><img src="${escape(article.image||'/assets/arctic-coast.webp')}" alt="${escape(article.caption||'Арктическое побережье')}" width="1280" height="720">${article.caption?`<figcaption>${escape(article.caption)}</figcaption>`:''}</figure>${article.sections.map(([title,body])=>`<section><h2>${escape(title)}</h2><p>${escape(body)}</p></section>`).join('')}<section><h2>Источники</h2><ul>${article.sources.map(([title,url])=>`<li><a href="${escape(url)}">${escape(title)}</a></li>`).join('')}</ul></section></article></main></div>`;
 const html=index.replace(/<title>.*?<\/title>/,`<title>${escape(article.title)} | Арктика</title>`).replace(/<meta name="description"[^>]+>/,`<meta name="description" content="${escape(article.intro)}">`).replace('</head>',`<link rel="canonical" href="${url}"><meta property="og:title" content="${escape(article.title)}"><meta property="og:description" content="${escape(article.intro)}"><meta property="og:image" content="${image}"><meta property="og:type" content="article"><script type="application/ld+json">${schema}</script></head>`).replace('<div id="app"></div>',content);
 const directory=path.join('dist/materials',slug);await fs.mkdir(directory,{recursive:true});await fs.writeFile(path.join(directory,'index.html'),html);
}
console.log('Prerendered 7 articles with SEO metadata and complete HTML');

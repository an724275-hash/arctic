# 40 правок сайта

Внесены 14.10.2026 18:53 (Якутск). Все пункты — реальные новые изменения этого пакета; прежние правки в счёт не включены.

1. Счётчик этапа: увеличил шрифт с 12 до 13 px. Файл: `frontend/src/refinements.css`; элемент: `.stage-count`.
2. Подпись состояния задачи: увеличил шрифт с 11 до 12 px. Файл: `frontend/src/refinements.css`; элемент: `.task-state`.
3. Описание этапа: увеличил шрифт с 14 до 15 px. Файл: `frontend/src/refinements.css`; элемент: `.stage-description`.
4. Пояснения условий: увеличил шрифт с 14 до 15 px. Файл: `frontend/src/refinements.css`; элемент: `.stage-requirements p`.
5. Разрешил перенос элементов шапки этапа при нехватке места. Файл: `frontend/src/refinements.css`; элемент: `.stage-window>header`.
6. Добавил перенос длинных слов в заголовках этапов. Файл: `frontend/src/refinements.css`; элемент: `.stage-window h3`.
7. Увеличил маркеры задач до 16 px и совместил с соединительной линией. Файл: `frontend/src/refinements.css`; элемент: `.task-node`.
8. Увеличил толщину полосы прогресса с 3 до 4 px. Файл: `frontend/src/refinements.css`; элемент: `.stage-meter`.
9. Увеличил область ссылки задачи: минимум 112 px на широком экране и 76 px на телефоне. Файл: `frontend/src/refinements.css`; элемент: `.stage-tasks li>a`.
10. Уменьшил радиус фотографии статьи до 8 px. Файл: `frontend/src/refinements.css`; элемент: `.article-hero img`.
11. Подпись фотографии: увеличил шрифт с 12 до 14 px. Файл: `frontend/src/refinements.css`; элемент: `.article-hero figcaption`.
12. Уменьшил радиус блока содержания статьи с 20 до 6 px. Файл: `frontend/src/refinements.css`; элемент: `.article-toc`.
13. Убрал декоративную нумерацию и левый отступ содержания статьи. Файл: `frontend/src/refinements.css`; элемент: `.article-toc ol`.
14. Выровнял длинные кнопки содержания статьи по левому краю. Файл: `frontend/src/refinements.css`; элемент: `.article-toc button`.
15. Уменьшил радиус нижнего блока статьи с 20 до 8 px. Файл: `frontend/src/refinements.css`; элемент: `.reading-next`.
16. Уменьшил радиус ответов в разделе помощи с 14 до 6 px. Файл: `frontend/src/refinements.css`; элемент: `.help-questions details`.
17. Добавил синюю боковую отметку раскрытому ответу помощи; зарезервировал место, чтобы текст не прыгал. Файл: `frontend/src/refinements.css`; элемент: `.help-questions details[open]`.
18. Добавил постоянное подчёркивание ссылок на источники. Файл: `frontend/src/refinements.css`; элемент: `.article-sources a`.
19. Добавил безопасный перенос длинного текста в абзацах статей. Файл: `frontend/src/refinements.css`; элемент: `.reading-page p`.
20. Уменьшил заголовки новостей с 28 до 26 px, на телефоне до 23 px. Файл: `frontend/src/refinements.css`; элемент: `.news-list h2`.
21. Увеличил максимальную ширину обложки новости с 680 до 780 px. Файл: `frontend/src/refinements.css`; элемент: `.news-cover`.
22. Увеличил шрифт подсказок форм с 12 до 13 px. Файл: `frontend/src/refinements.css`; элемент: `.form-caption`.
23. Уменьшил радиус пустых состояний кабинета с 16 до 6 px. Файл: `frontend/src/refinements.css`; элемент: `.console-empty`.
24. Уменьшил заголовки уведомлений с 21 до 19 px. Файл: `frontend/src/refinements.css`; элемент: `.notification-item h2`.
25. Закрепил шапку таблицы и ограничил область прокрутки высотой 60vh, не более 640 px. Файл: `frontend/src/refinements.css`; элемент: `.console-table-wrap / .console-table th`.
26. Уменьшил радиус окна предпросмотра PDF с 12 до 4 px. Файл: `frontend/src/refinements.css`; элемент: `.certificate-preview`.
27. Сделал затемнение под диалогом мягче: opacity 0.38 вместо прежних примерно 0.52. Файл: `frontend/src/refinements.css`; элемент: `dialog::backdrop`.
28. Увеличил область кнопки «Выйти» в подвале до 44 px. Файл: `frontend/src/refinements.css`; элемент: `.footer-links>button`.
29. Указал асинхронное декодирование изображений сайта. Файл: `frontend/src/ux.js`; элемент: `img[decoding]`.
30. Задал высокий приоритет загрузки главного фонового изображения. Файл: `frontend/src/views.js`; элемент: `.cover-landscape[fetchpriority]`.
31. Заменил отложенную загрузку главной фотографии статьи на немедленную. Файл: `frontend/src/public-views.js`; элемент: `.article-hero img[loading]`.
32. Добавил мобильные варианты обложек новостей через srcset; вынес проверенные размеры в общий помощник. Файл: `frontend/src/images.js + frontend/src/product-views.js`; элемент: `.news-cover[srcset]`.
33. Добавил отметку текущей страницы для всех пунктов верхней навигации. Файл: `frontend/src/ux.js`; элемент: `.navigation [aria-current]`.
34. Отключил автозаглавные буквы, автокоррекцию и проверку орфографии в полях почты. Файл: `frontend/src/ux.js`; элемент: `input[type=email]`.
35. Ограничил новый пароль при восстановлении 256 символами, как на сервере. Файл: `frontend/src/ux.js`; элемент: `input[type=password][maxlength]`.
36. Сделал корректный порядок Tab: среди вкладок настроек в него входит только выбранная. Файл: `frontend/src/ux.js`; элемент: `[role=tab][tabindex]`.
37. Добавил управление вкладками стрелками, Home и End с сохранением фокуса после переключения. Файл: `frontend/src/ux.js`; элемент: `keydown [role=tab]`.
38. Добавил закрытие подсказок города по клику снаружи без очистки введённого города. Файл: `frontend/src/ux.js`; элемент: `#city-options`.
39. Добавил машиночитаемый datetime к датам публикации новостей. Файл: `frontend/src/product-views.js`; элемент: `.news-list time[datetime]`.
40. Для пройденного этапа показываю «Проходной результат достигнут», чтобы новая настройка порога не противоречила старому результату. Файл: `frontend/src/contest-path.js`; элемент: `Результат`.

Проверка: сборка frontend, 81 UX-сценарий, 36 вариантов публичных страниц без переполнения и битых изображений, восемь дополнительных браузерных проверок. Новых серверных изменений в этом пакете нет; 89 серверных тестов относятся к предыдущему завершённому пакету.

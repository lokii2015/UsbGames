UsbGames gift cards — quick guide
================================

Format: USB-Cxxx-xxxx-xxxx-x  (store credit at Checkout only)

YOUR WORKFLOW
-------------
1) Generate codes for printing:
     node tools/gift-card-maker.js gen 15
   (or double-click GiftCardMaker.exe gen 15)

   Opens tools/codes-to-print.txt — put each code on a physical card.

2) Link money (CAD) — activates codes on the website:
     node tools/gift-card-maker.js link tools/codes-to-print.txt 25
   (all 15 codes = $25.00 CAD each)

   Or different amounts per line in a text file:
     USB-C7YK-F8MA-HEYD-H 25
     USB-CABC-DEFG-HIJK-L 50
     node tools/gift-card-maker.js link my-list.txt

3) Put on LIVE site (Render):
     node tools/gift-card-maker.js push https://usbgames.onrender.com 5394
   (5394 = your FAQ_ADMIN_CODE from checkout/.env / Render)

Customers use codes at: Checkout → Gift card tab
Check balance at: Orders page → Gift card balance

Already have 15 codes?
----------------------
Paste them in tools/codes-to-print.txt (one per line), then:
  node tools/gift-card-maker.js link tools/codes-to-print.txt 25
  node tools/gift-card-maker.js push https://usbgames.onrender.com YOUR_CODE

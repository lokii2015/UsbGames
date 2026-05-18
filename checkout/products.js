/** Premium products — amounts in cents (CAD). */
const STORE_CURRENCY = "cad";

function formatPriceLabel(product) {
  const cur = (product.currency || STORE_CURRENCY).toUpperCase();
  return `$${(product.amount / 100).toFixed(2)} ${cur}`;
}

const PRODUCTS = {
  snake_deluxe: {
    id: "snake_deluxe",
    name: "Snake Deluxe",
    description: "Premium Snake — skins, speed modes, wall & portal maps",
    amount: 199,
    currency: STORE_CURRENCY,
    files: ["SnakeDeluxe.zip"],
  },
  pixel_flap_turbo: {
    id: "pixel_flap_turbo",
    name: "Pixel Flap Turbo",
    description: "Turbo flap — power-ups, levels, moving obstacles",
    amount: 199,
    currency: STORE_CURRENCY,
    files: ["PixelFlapTurbo.zip"],
  },
  tictactoe_aiplus: {
    id: "tictactoe_aiplus",
    name: "Tic-Tac-Toe AI+",
    description: "Deluxe tic-tac-toe — easy, medium & hard AI (minimax), stats",
    amount: 199,
    currency: STORE_CURRENCY,
    files: ["TicTacToeAIPlus.zip"],
  },
  grid_defense: {
    id: "grid_defense",
    name: "Grid Defense",
    description: "Tower defense — blasters, cannons, endless waves",
    amount: 199,
    currency: STORE_CURRENCY,
    files: ["GridDefense.zip"],
  },
  pixel_kart: {
    id: "pixel_kart",
    name: "Pixel Kart",
    description: "Top-down kart racing — 4 tracks, items, AI rivals",
    amount: 249,
    currency: STORE_CURRENCY,
    files: ["PixelKart.zip"],
  },
  pocket_rpg: {
    id: "pocket_rpg",
    name: "Pocket RPG",
    description: "Mini JRPG — battles, shop, inventory, saves",
    amount: 199,
    currency: STORE_CURRENCY,
    files: ["PocketRPG.zip"],
  },
  blockstack_dx: {
    id: "blockstack_dx",
    name: "BlockStack DX",
    description: "Retro falling-block puzzle — classic & speed, combos, neon themes",
    amount: 499,
    currency: STORE_CURRENCY,
    files: ["BlockStackDX.zip"],
  },
  pixel_chomp: {
    id: "pixel_chomp",
    name: "Pixel Chomp",
    description: "Maze chase — dots, power pellets, four ghost AIs",
    amount: 799,
    currency: STORE_CURRENCY,
    files: ["PixelChomp.zip"],
  },
  black_jack: {
    id: "black_jack",
    name: "Black Jack",
    description: "Retro casino blackjack — bet, hit, stand, double down, USB stats",
    amount: 599,
    currency: STORE_CURRENCY,
    files: ["BlackJack.zip"],
  },
  starter_pack: {
    id: "starter_pack",
    name: "UsbGames Starter Pack",
    description: "Snake Deluxe + Pixel Flap Turbo + Tic-Tac-Toe AI+ — save vs separate",
    amount: 499,
    currency: STORE_CURRENCY,
    files: ["UsbGames-StarterPack.zip"],
  },
  retro_arcade_pack: {
    id: "retro_arcade_pack",
    name: "Retro Arcade Pack",
    description: "Grid Defense + Pixel Kart + Pocket RPG — save $0.99",
    amount: 548,
    currency: STORE_CURRENCY,
    files: ["UsbGames-RetroArcadePack.zip"],
  },
};

function getProduct(productId) {
  return PRODUCTS[productId] || null;
}

function listProducts() {
  return Object.values(PRODUCTS);
}

function resolveCart(productIds) {
  if (!Array.isArray(productIds) || productIds.length === 0) return null;
  const items = [];
  const seen = new Set();
  for (const raw of productIds) {
    const id = String(raw || "").trim();
    if (!id || seen.has(id)) continue;
    const p = getProduct(id);
    if (!p) return null;
    seen.add(id);
    items.push(p);
  }
  if (items.length === 0) return null;
  const currency = items[0].currency || STORE_CURRENCY;
  for (const p of items) {
    if ((p.currency || STORE_CURRENCY) !== currency) return null;
  }
  const amount = items.reduce((s, p) => s + p.amount, 0);
  const files = [];
  const fileSeen = new Set();
  for (const p of items) {
    for (const f of p.files) {
      if (!fileSeen.has(f)) {
        fileSeen.add(f);
        files.push(f);
      }
    }
  }
  return {
    items,
    productIds: items.map((p) => p.id),
    name:
      items.length === 1
        ? items[0].name
        : `UsbGames order (${items.length} items)`,
    description: items.map((p) => p.name).join(", "),
    amount,
    currency,
    priceLabel: `$${(amount / 100).toFixed(2)} ${currency.toUpperCase()}`,
    files,
  };
}

module.exports = {
  PRODUCTS,
  STORE_CURRENCY,
  getProduct,
  listProducts,
  resolveCart,
  formatPriceLabel,
};

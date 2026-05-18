/**
 * Product catalog — keep in sync with checkout/products.js
 * Used client-side so cart/checkout work even before API loads.
 */
(function (root) {
  const STORE_CURRENCY = "cad";

  const CATALOG = {
    snake_deluxe: {
      id: "snake_deluxe",
      name: "Snake Deluxe",
      description: "Premium Snake — skins, speed modes, wall & portal maps",
      amount: 199,
      currency: STORE_CURRENCY,
    },
    pixel_flap_turbo: {
      id: "pixel_flap_turbo",
      name: "Pixel Flap Turbo",
      description: "Turbo flap — power-ups, levels, moving obstacles",
      amount: 199,
      currency: STORE_CURRENCY,
    },
    tictactoe_aiplus: {
      id: "tictactoe_aiplus",
      name: "Tic-Tac-Toe AI+",
      description: "Deluxe tic-tac-toe — easy, medium & hard AI",
      amount: 199,
      currency: STORE_CURRENCY,
    },
    grid_defense: {
      id: "grid_defense",
      name: "Grid Defense",
      description: "Tower defense — blasters, cannons, endless waves",
      amount: 199,
      currency: STORE_CURRENCY,
    },
    pixel_kart: {
      id: "pixel_kart",
      name: "Pixel Kart",
      description: "Top-down kart racing — 4 tracks, items, AI rivals",
      amount: 249,
      currency: STORE_CURRENCY,
    },
    pocket_rpg: {
      id: "pocket_rpg",
      name: "Pocket RPG",
      description: "Mini JRPG — battles, shop, inventory, saves",
      amount: 199,
      currency: STORE_CURRENCY,
    },
    blockstack_dx: {
      id: "blockstack_dx",
      name: "BlockStack DX",
      description: "Retro falling-block puzzle — classic & speed, combos, neon themes",
      amount: 499,
      currency: STORE_CURRENCY,
    },
    pixel_chomp: {
      id: "pixel_chomp",
      name: "Pixel Chomp",
      description: "Maze chase — dots, power pellets, four ghost AIs",
      amount: 799,
      currency: STORE_CURRENCY,
    },
    black_jack: {
      id: "black_jack",
      name: "Black Jack",
      description: "Retro casino blackjack — bet, hit, stand, double down, USB stats",
      amount: 599,
      currency: STORE_CURRENCY,
    },
    starter_pack: {
      id: "starter_pack",
      name: "UsbGames Starter Pack",
      description: "Snake Deluxe + Pixel Flap Turbo + Tic-Tac-Toe AI+",
      amount: 499,
      currency: STORE_CURRENCY,
    },
    retro_arcade_pack: {
      id: "retro_arcade_pack",
      name: "Retro Arcade Pack",
      description: "Grid Defense + Pixel Kart + Pocket RPG",
      amount: 548,
      currency: STORE_CURRENCY,
    },
  };

  function formatPrice(cents, currency) {
    const cur = (currency || STORE_CURRENCY).toUpperCase();
    return "$" + (cents / 100).toFixed(2) + " " + cur;
  }

  function formatCartTotal(lines) {
    if (!lines || lines.length === 0) return formatPrice(0, STORE_CURRENCY);
    const cur = lines[0].currency || STORE_CURRENCY;
    const total = lines.reduce((s, p) => s + p.amount, 0);
    return formatPrice(total, cur);
  }

  function getProduct(id) {
    const p = CATALOG[id];
    if (!p) return null;
    const currency = p.currency || STORE_CURRENCY;
    return {
      ...p,
      currency,
      priceLabel: formatPrice(p.amount, currency),
    };
  }

  function listProducts() {
    return Object.values(CATALOG).map((p) => getProduct(p.id));
  }

  root.UsbGamesCatalog = {
    CATALOG,
    STORE_CURRENCY,
    getProduct,
    listProducts,
    formatPrice,
    formatCartTotal,
  };
})(typeof window !== "undefined" ? window : globalThis);

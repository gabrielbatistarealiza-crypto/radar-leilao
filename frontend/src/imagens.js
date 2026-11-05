// Fotos dos anúncios: reduzir no aparelho antes de enviar e montar o endereço completo.
import { API_URL } from "./api";

export const MAX_FOTOS = 10;
const LADO_MAXIMO = 1600; // px no lado maior
const QUALIDADE = 0.82; // JPEG

/** Fotos carregadas têm um caminho da API ("/anuncios-imoveis/fotos/..."); as outras, um link. */
export function urlDaFoto(url) {
  if (!url) return null;
  return url.startsWith("/") ? `${API_URL}${url}` : url;
}

async function abrirImagem(ficheiro) {
  if (typeof createImageBitmap === "function") {
    // imageOrientation: respeita a rotação das fotos tiradas com o telemóvel.
    return createImageBitmap(ficheiro, { imageOrientation: "from-image" });
  }
  const url = URL.createObjectURL(ficheiro);
  try {
    const img = new Image();
    img.src = url;
    await img.decode();
    return img;
  } finally {
    URL.revokeObjectURL(url);
  }
}

/**
 * Reduz a foto (lado maior até 1600 px) e devolve-a como "data:image/jpeg;base64,...".
 * Lança Error com uma mensagem legível se o ficheiro não for uma imagem.
 */
export async function reduzirImagem(ficheiro) {
  if (!ficheiro?.type?.startsWith("image/")) {
    throw new Error(`"${ficheiro?.name || "ficheiro"}" não é uma imagem.`);
  }
  let imagem;
  try {
    imagem = await abrirImagem(ficheiro);
  } catch {
    throw new Error(`Não foi possível abrir "${ficheiro.name}". Experimente uma foto JPG ou PNG.`);
  }
  const largura = imagem.width;
  const altura = imagem.height;
  const escala = Math.min(1, LADO_MAXIMO / Math.max(largura, altura));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(largura * escala);
  canvas.height = Math.round(altura * escala);
  const contexto = canvas.getContext("2d");
  contexto.fillStyle = "#fff"; // PNG transparente fica com fundo branco no JPEG
  contexto.fillRect(0, 0, canvas.width, canvas.height);
  contexto.drawImage(imagem, 0, 0, canvas.width, canvas.height);
  imagem.close?.();
  return canvas.toDataURL("image/jpeg", QUALIDADE);
}

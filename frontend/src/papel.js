// Papel do utilizador (cliente, corretor, admin) e os nomes que se mostram no ecrã.

export const ROTULOS_PAPEL = {
  cliente: "Cliente",
  corretor: "Corretor",
  admin: "Administrador",
};

export function papelDoUsuario(usuario) {
  if (usuario?.admin === true || usuario?.tipo === "admin") {
    return "admin";
  }

  return ["cliente", "corretor"].includes(usuario?.tipo)
    ? usuario.tipo
    : null;
}

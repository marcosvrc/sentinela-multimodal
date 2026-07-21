/**
 * @deprecated Substituido por `useDevSession`. O backend nao aceita mais
 * `institution_id` vindo do cliente; a instituicao agora e resolvida a
 * partir do usuario autenticado
 * (`X-Dev-Subject`). Mantido apenas como re-export para nao deixar um
 * arquivo orfao no historico; novo codigo deve importar `useDevSession`
 * diretamente.
 */
export { useDevSession as useDevInstitution } from "./useDevSession";

interface LogoProps {
  className?: string;
}

/**
 * Simbolo de marca proprio (SVG, sem dependencia de fonte de icones ou
 * emoji): um pulso/onda de sinal vital dentro de um escudo arredondado -
 * referencia visual a "sentinela" (vigilancia) + "health" (sinal
 * clinico), nao reaproveita nenhum ativo de terceiros.
 */
export function Logo({ className }: LogoProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <rect width="32" height="32" rx="8" fill="currentColor" fillOpacity="0.12" />
      <path
        d="M6 17h4l2.5-5 3 9 2.5-6H26"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

import logoDark from '../../../assets/brand/taleport-logo-dark.svg?url'
import logoLight from '../../../assets/brand/taleport-logo-light.svg?url'

/** Full TALeport wordmark; swaps file with the active theme. */
export function Logo({ className = '' }: { className?: string }) {
  return (
    <>
      <img src={logoDark} alt="TALeport" className={`light:hidden ${className}`} />
      <img src={logoLight} alt="TALeport" className={`hidden light:block ${className}`} />
    </>
  )
}

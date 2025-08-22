import '../ui/global.css'
import Link from 'next/link'

export function Footer() {
    return (
        <footer>
            <p>© John Yeung 2024 - 2025</p>
        </footer>
    )
}

export function Header() {
    return (
        <header className='top'>
            <div className='header-img'><Link className='home-link' href='/'>Agent Based Simulator</Link></div>
            <div className='login'></div>
        </header>
    )   
}
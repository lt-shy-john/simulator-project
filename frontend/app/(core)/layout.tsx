import '../ui/global.css'
import '../ui/home.module.css'
import { Header, Footer } from '../ui/global-components'

export default function RootLayout({
    children,
  }: {
    children: React.ReactNode
  }) {
    return (
      <html lang="en">
        <head>
          <meta charSet="UTF-8" />
          <meta name="viewport" content="width=device-width" />
          <link rel="icon" href="/favicon.ico"/>
          <title>Agent Based Simulator</title>
        </head>
        <body>
            <Header />
            {children}
            <Footer/>
        </body>
      </html>
    )
  }
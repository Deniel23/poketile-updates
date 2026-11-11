# PokéTile Discord Updates

Comprueba PokéTile cada 30 minutos y publica las notas oficiales en un canal de Discord cuando detecta una versión nueva.

## Configuración

1. En GitHub, abre **Settings → Secrets and variables → Actions**.
2. Crea un Repository Secret llamado `DISCORD_WEBHOOK` con la URL del webhook de Discord.
3. En **Actions**, habilita los workflows si GitHub lo solicita.
4. Ejecuta manualmente **PokéTile updates → Run workflow** una primera vez.

La primera ejecución guarda la versión actual como referencia y no publica el parche antiguo. Las siguientes ejecuciones publican el contenido de Novedades cuando cambia la versión.

## Importante

El sitio puede cambiar su diseño o la forma en que presenta las novedades. Si ocurre, la ejecución aparecerá como fallida en la pestaña Actions y habrá que ajustar el extractor.

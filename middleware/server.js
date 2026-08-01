require('dotenv').config()
const express = require('express')
const cors    = require('cors')
const app     = express()

app.use(cors())
app.use(express.json())

// Routes
app.use('/api/images',      require('./routes/images'))
app.use('/api/search',      require('./routes/search'))
app.use('/api/categories',  require('./routes/categories'))
app.use('/api/upload',      require('./routes/upload'))
app.use('/api/corrections', require('./routes/corrections'))
app.use('/api/clusters',    require('./routes/clusters'))
app.use('/api/pipeline',    require('./routes/pipeline'))
app.use('/api/stats',       require('./routes/stats'))

// Health check
app.get('/health', (req, res) => res.json({ status: 'ok' }))

const PORT = process.env.PORT || 3000
app.listen(PORT, () => console.log(`UKAHT middleware running on port ${PORT}`))

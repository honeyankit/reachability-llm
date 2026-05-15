// TRUE_POSITIVE example: invokes _.template() with user-controlled sourceURL
const _ = require('lodash');
const express = require('express');
const app = express();

function renderTemplate(templateStr, data, userSource) {
    // CVE-2021-23337: sourceURL flows from user-controlled req.query.src
    return _.template(templateStr, {
        sourceURL: userSource
    })(data);
}

function handleRender(req, res) {
    const html = renderTemplate(req.body.template, req.body.data, req.query.src);
    res.send(html);
}

app.post('/render', handleRender);

module.exports = { renderTemplate, handleRender };

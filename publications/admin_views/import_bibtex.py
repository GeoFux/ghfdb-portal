import re
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import HttpResponseRedirect
from publications.bibtex import parse
from publications.models import Publication, Type
from django.views.generic import TemplateView
from publications.forms import UploadForm
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.http import HttpResponse
from django.utils.translation import gettext as _

# mapping of months
MONTHS = {
    'jan': 1, 'january': 1,
    'feb': 2, 'february': 2,
    'mar': 3, 'march': 3,
    'apr': 4, 'april': 4,
    'may': 5,
    'jun': 6, 'june': 6,
    'jul': 7, 'july': 7,
    'aug': 8, 'august': 8,
    'sep': 9, 'september': 9,
    'oct': 10, 'october': 10,
    'nov': 11, 'november': 11,
    'dec': 12, 'december': 12}

@staff_member_required
def import_bibtex(request):
    if request.method == 'POST':
        # try to parse BibTex
        bib = parse(request.POST['bibliography'])

        # container for error messages
        errors = {}

        # publication types
        types = Type.objects.all()

        # check for errors
        if not bib:
            if not request.POST['bibliography']:
                errors['bibliography'] = 'This field is required.'

        if not errors:
            publications = []

            # try adding publications
            for entry in bib:
                if 'title' in entry and \
                   'author' in entry and \
                   'year' in entry:
                    # parse authors
                    authors = entry['author'].split(' and ')
                    for i in range(len(authors)):
                        author = authors[i].split(',')
                        author = [author[-1]] + author[:-1]
                        authors[i] = ' '.join(author)
                    authors = ', '.join(authors)

                    # add missing keys
                    keys = [
                        'journal',
                        'booktitle',
                        'publisher',
                        'institution',
                        'url',
                        'doi',
                        'isbn',
                        'keywords',
                        'pages',
                        'note',
                        'abstract',
                        'month']

                    for key in keys:
                        if not key in entry:
                            entry[key] = ''

                    # map integer fields to integers
                    entry['month'] = MONTHS.get(entry['month'].lower(), 0)

                    entry['volume'] = entry.get('volume', None)
                    entry['number'] = entry.get('number', None)

                    if isinstance(entry['volume'], str):
                        entry['volume'] = int(re.sub('[^0-9]', '', entry['volume']))
                    if isinstance(entry['number'], str):
                        entry['number'] = int(re.sub('[^0-9]', '', entry['number']))

                    # remove whitespace characters (likely due to line breaks)
                    entry['url'] = re.sub(r'\s', '', entry['url'])

                    # determine type
                    type_id = None

                    for t in types:
                        if entry['type'] in t.bibtex_type_list:
                            type_id = t.id
                            break

                    if type_id is None:
                        errors['bibliography'] = 'Type "' + entry['type'] + '" unknown.'
                        break

                    # add publication
                    publications.append(Publication(
                        type_id=type_id,
                        citekey=entry['key'],
                        title=entry['title'],
                        authors=authors,
                        year=entry['year'],
                        month=entry['month'],
                        journal=entry['journal'],
                        book_title=entry['booktitle'],
                        publisher=entry['publisher'],
                        institution=entry['institution'],
                        volume=entry['volume'],
                        number=entry['number'],
                        pages=entry['pages'],
                        note=entry['note'],
                        url=entry['url'],
                        doi=entry['doi'],
                        isbn=entry['isbn'],
                        abstract=entry['abstract'],
                        keywords=entry['keywords']))
                else:
                    errors['bibliography'] = 'Make sure that the keys title, author and year are present.'
                    break

        if not errors and not publications:
            errors['bibliography'] = 'No valid BibTex entries found.'

        if errors:
            # some error occurred
            return render(
                request,
                'admin/publications/import_bibtex.html', {
                    'errors': errors,
                    'title': 'Import BibTex',
                    'types': Type.objects.all(),
                    'request': request})
        else:
            try:
                # save publications
                for publication in publications:
                    publication.save()
            except:
                msg = 'Some error occured during saving of publications.'
            else:
                if len(publications) > 1:
                    msg = 'Successfully added ' + str(len(publications)) + ' publications.'
                else:
                    msg = 'Successfully added ' + str(len(publications)) + ' publication.'

            # show message
            messages.info(request, msg)

            # redirect to publication listing
            if len(publications) == 1:
                return HttpResponseRedirect('../%s/change/' % publications[0].id)
            else:
                return HttpResponseRedirect('../')
    else:
        return render(
            request,
            'admin/publications/import_bibtex.html', {
                'title': 'Import BibTex',
                'types': Type.objects.all(),
                'request': request})


class ImportBibtex(TemplateView):
    template_name = 'admin/publications/import_bibtex.html'
    confirm_template_name = 'upload_confirm.html'
    form = UploadForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(dict(
            form = self.form,
            title='Import Bibtex',
            types = Type.objects.all(),
        ))
        return context

    @method_decorator(require_POST)
    def post(self, request, *args, **kwargs):
        context = super().get_context_data(**kwargs)

        form = self.form(request.POST, request.FILES)
        if form.is_valid():
            # submitted form is valid so temporarily save data to cache for later use
            imported_file = form.cleaned_data.pop('file')

            # read in the dataset
            bibtex = self.get_dataset(imported_file)
            # A HTTPResponse will be returned if an error is enounctered reading the file
            if isinstance(bibtex, HttpResponse):
                return bibtex 

            bib = parse(bibtex)

            # container for error messages
            errors = []
            publications = []

            # try adding publications
            for i, entry in enumerate(bib):

                cleaned = entry.copy()

                # parse authors
                authors = cleaned['author'].split(' and ')
                for i in range(len(authors)):
                    author = authors[i].split(',')
                    author = [author[-1]] + author[:-1]
                    authors[i] = ' '.join(author)
                authors = ', '.join(authors)

                # add missing keys
                keys = [
                    'journal',
                    'booktitle',
                    'publisher',
                    'institution',
                    'url',
                    'doi',
                    'isbn',
                    'keywords',
                    'pages',
                    'note',
                    'abstract',
                    'month']

                for key in keys:
                    if not key in entry:
                        cleaned[key] = ''

                # map integer fields to integers
                cleaned['month'] = MONTHS.get(cleaned['month'].lower(), 0)
                cleaned['volume'] = cleaned.get('volume', None)
                cleaned['number'] = cleaned.get('number', None)


                for field in ['volume', 'number']:
                    entry[field] = entry.get(field, None)
               



                # remove whitespace characters (likely due to line breaks)
                cleaned['url'] = re.sub(r'\s', '', cleaned['url'])

                # determine type
                type_id = None
                for t in Type.objects.all():
                    if cleaned['type'] in t.bibtex_type_list():
                        type_id = t.id
                        break

                if type_id is None:
                    errors.append(dict(entry=entry,
                        message='Type "' + entry['type'] + '" unknown.'
                        ))

                # add publication
                publications.append(Publication(
                    type_id=type_id,
                    citekey=cleaned['key'],
                    title=cleaned['title'],
                    authors=authors,
                    year=cleaned['year'],
                    month=cleaned['month'],
                    journal=cleaned['journal'],
                    book_title=cleaned['booktitle'],
                    publisher=cleaned['publisher'],
                    institution=cleaned['institution'],
                    volume=cleaned['volume'],
                    number=cleaned['number'],
                    pages=cleaned['pages'],
                    note=cleaned['note'],
                    url=cleaned['url'],
                    doi=cleaned['doi'],
                    isbn=cleaned['isbn'],
                    abstract=cleaned['abstract'],
                    keywords=cleaned['keywords']))

            if errors:
                # some error occurred
                return render(
                    request,
                    'admin/publications/import_bibtex.html', {
                        'errors': errors,
                        'title': 'Import BibTex',
                        'types': Type.objects.all(),
                        'request': request})
            else:
                try:
                    # save publications
                    for publication in publications:
                        publication.save()
                except Exception as e:
                    msg = e
                else:
                    if len(publications) > 1:
                        msg = 'Successfully added ' + str(len(publications)) + ' publications.'
                    else:
                        msg = 'Successfully added ' + str(len(publications)) + ' publication.'

                # show message
                messages.info(request, msg)

                # redirect to publication listing
                if len(publications) == 1:
                    return HttpResponseRedirect(f'../{publications[0].id}/change/')
                else:
                    return HttpResponseRedirect('../')




    def get_dataset(self, data_file):
        try:
            data = data_file.read().decode('utf-8')
        except UnicodeDecodeError as e:
            return HttpResponse(_(u"<h1>Imported file has a wrong encoding: {}</h1>".format(e)))
        except Exception as e:
            return HttpResponse(_(u"<h1>{} encountered while trying to read file: {}</h1>".format(type(e).__name__)))

        return data


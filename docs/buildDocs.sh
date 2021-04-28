#!/bin/bash
# set -x
################################################################################
# File:    buildDocs.sh
# Purpose: Script that builds our documentation using sphinx and updates GitHub
#          Pages. This script is executed by:
#            .github/workflows/*.yml
#
# Authors: Michael Altfield <michael@michaelaltfield.net>
#          Paul Saxe <psaxe@vt.edu>
# Created: 2020-07-17
# Updated: 2020-12-12
# Version: 0.3
################################################################################
 
#####################
# DECLARE VARIABLES #
#####################
 
echo "::group::Setup"
pwd
ls -lah
export SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct)
 
# make a new temp dir which will be our GitHub Pages docroot
docroot=`mktemp -d`
mkdir "${docroot}/dev"

export REPO_NAME="${GITHUB_REPOSITORY##*/}"
echo "::endgroup::"
 
##############
# BUILD DOCS #
##############

echo "::group::Branches"
# get a list of branches, excluding 'HEAD' and 'gh-pages'
versions="`git for-each-ref '--format=%(refname:lstrip=-1)' refs/remotes/origin/ | grep -viE '^(HEAD|gh-pages)$'`"
echo "Branches to document"
for current_version in ${versions}
do
    echo "       ${current_version}"
done
echo "::endgroup::"

for current_version in ${versions}
do
    echo "::group::Documentation for ${current_version} branch"
 
    # make the current language available to conf.py
    export current_version
    git checkout ${current_version}
 
    # skip this branch if it doesn't have our docs dir & sphinx config
    if [ ! -e 'docs/conf.py' ]; then
	echo "::warning::Skipping because could not find 'docs/conf.py'"
	continue
    fi

    # Install this version so the documentation for the API works
    python -m pip install . --no-deps
 
    languages="en `find docs/locales/ -mindepth 1 -maxdepth 1 -type d -exec basename '{}' \;`"
    for current_language in ${languages}
    do
	# make the current language available to conf.py
	export current_language
	
	##########
	# BUILDS #
	##########
	echo "Building for ${current_language}"

	# first, cleanup any old builds' static assets
	make -C docs clean

	# Build the documentation for the code
	sphinx-apidoc -o docs/developer seamm

	# HTML #
	sphinx-build -b html docs/ docs/_build/html/${current_language}/${current_version} -D language="${current_language}"
	
	# # PDF #
	# sphinx-build -b rinoh docs/ docs/_build/rinoh -D language="${current_language}"
	# mkdir -p "${docroot}/${current_language}/${current_version}"
	# cp "docs/_build/rinoh/target.pdf" "${docroot}/${current_language}/${current_version}/helloWorld-docs_${current_language}_${current_version}.pdf"
	
	# # EPUB #
	# sphinx-build -b epub docs/ docs/_build/epub -D language="${current_language}"
	# mkdir -p "${docroot}/${current_language}/${current_version}"
	# cp "docs/_build/epub/target.epub" "${docroot}/${current_language}/${current_version}/helloWorld-docs_${current_language}_${current_version}.epub"
	
	# copy the static assets produced by the above build into our docroot
	if [ "${current_version}" = "main" -a "${current_language}" = "en" ]
	then
	    echo "Publishing main to /"
	    rsync -a "docs/_build/html/en/main/" "${docroot}/"
	else
	    echo "Publishing ${current_version} to /dev/${current_language}/${current_version}/"
	    rsync -a "docs/_build/html/" "${docroot}/dev/"
	fi
    done
    echo "::endgroup::"
done
 
#######################
# Update GitHub Pages #
#######################
echo "::group::Create index files, etc."
 
# return to main branch
git checkout main
 
git config --global user.name "${GITHUB_ACTOR}"
git config --global user.email "${GITHUB_ACTOR}@users.noreply.github.com"
 
# add redirect from the docroot to our default docs language/version
cat > "${docroot}/dev/index.html" <<EOF
<!DOCTYPE html>
<html>
   <head>
      <title>Documentation for the SEAMM module in SEAMM</title>
   </head>
   <body>
      <h1>Documentation for the SEAMM module in SEAMM</h1>
      <h2>Branches</h2>
      <ul>
EOF

cat > "${docroot}/dev/versions.html" <<EOF
<!DOCTYPE html>
<html>
   <head>
      <title>Documentation for the SEAMM module in SEAMM</title>
   </head>
   <body>
      <ul>
EOF

for current_version in ${versions}
do
    if [ "${current_version}" = "main" ]
    then
	cat >> "${docroot}/dev/index.html" <<EOF
        <li><a href="../">main -- stable version</a></li>
EOF
	cat >> "${docroot}/dev/versions.html" <<EOF
        <li><a href="../" target="_parent">main -- stable version</a></li>
EOF
    fi
done

for current_version in ${versions}
do
    git checkout --no-guess ${current_version}

    # skip this branch if it doesn't have our docs dir & sphinx config
    if [ ! -e 'docs/conf.py' ]; then
	continue
    fi
    if [ "${current_version}" != "main" ]
    then
	cat >> "${docroot}/dev/index.html" <<EOF
        <li><a href="en/${current_version}/">${current_version}</a></li>
EOF
	cat >> "${docroot}/dev/versions.html" <<EOF
        <li><a href="en/${current_version}/" target="_parent">${current_version}</a></li>
EOF
    fi
done

cat >> "${docroot}/dev/index.html" <<EOF
      </ul>
   </body>
</html>
EOF
 
cat >> "${docroot}/dev/versions.html" <<EOF
      </ul>
   </body>
</html>
EOF
 
# add .nojekyll to the root so that github won't 404 on content added to dirs
# that start with an underscore (_), such as our "_content" dir..
touch ${docroot}/.nojekyll
 
# Add README
cat > ${docroot}/README.md <<EOF
# GitHub Pages Cache
 
Nothing to see here. The contents of this branch are essentially a cache that's not intended to be viewed on github.com.
 
 
If you're looking to update our documentation, check the relevant development branch's 'docs/' dir.
 
For more information on how this documentation is built using Sphinx, Read the Docs, and GitHub Actions/Pages, see:
 
 * https://tech.michaelaltfield.net/2020/07/18/sphinx-rtd-github-pages-1
EOF

echo "::endgroup::"
echo "::group::Push to gh-pages"

# Now go to the directory...
pushd "${docroot}"

# don't bother maintaining history; just generate fresh
git init
git remote add deploy "https://token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
git checkout -b gh-pages
 
# copy the resulting html pages built from sphinx above to our new git repo
git add .
 
# commit all the new files
msg="Updating Docs for commit ${GITHUB_SHA} made on `date -d"@${SOURCE_DATE_EPOCH}" --iso-8601=seconds` from ${GITHUB_REF} by ${GITHUB_ACTOR}"
git commit -am "${msg}"
 
# overwrite the contents of the gh-pages branch on our github.com repo
git push deploy gh-pages --force

popd # return to main repo sandbox root
echo "::endgroup::" 

echo "All done! Documentation built successfully."

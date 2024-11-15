#!/bin/bash
BUCKET=cse-kubarozek-sandbox-ariel-us
BUCKET_PATH="gs://$BUCKET/test-shell"

gsutil -m rm -r $BUCKET_PATH

gsutil cp gs://$BUCKET/input.mp4 $BUCKET_PATH/input.mp4

gsutil cp config.json $BUCKET_PATH/config.json

for i in {1..60}; do
  gsutil -q stat $BUCKET_PATH/utterances.json && break || echo -n "." && sleep 10; done
gsutil -q stat $BUCKET_PATH/utterances.json && gsutil cp $BUCKET_PATH/utterances.json $BUCKET_PATH/utterances_approved.json || echo "Utterances not produced within 10 minutes"
echo "DONE"
